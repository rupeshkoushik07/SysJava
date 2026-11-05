#!/usr/bin/env python3
"""Inventory ELF files in running containers and resolve their debug symbols.

Three-stage pipeline per container:

  1. Inventory: stream `docker export` as a tar and record (path, size, GNU
     Build ID) for every ELF file. Docker's export omits mounted volumes, so
     volumes-only content is invisible here -- an acceptable loss given the
     cost of bind-mounting an exploded rootfs.

  2. debuginfod: for each unique Build ID, ask the configured mirrors
     (DEBUGINFOD_URLS or the public set below) for a verified .debug.

  3. Container fallback: for Build IDs debuginfod misses, call
     install_container_dbgsym.sh inside the container to install the distro's
     dbgsym/debuginfo package pinned to the installed version, then tar
     /usr/lib/debug/.build-id back out. Build IDs that don't match on
     re-check are discarded.

Output layout under `artifacts/all-running-containers/debug-symbols/`:

  build-id/<id>.debug                  flat pool, one copy per Build ID
  usr/lib/debug/.build-id/XX/YY.debug  symlinks into the pool -- egalito's
                                       alternative-symbol-file lookup expects
                                       this layout (ElfSpace::getAlternative
                                       SymbolFile in SysPartCode)
  elf_inventory.tsv                    per-ELF rows across all containers
  symbol_manifest.tsv                  per-Build-ID final status
  missing_by_target/<target>.tsv       libs that still have no .debug after
                                       both A and B, scoped to targets that
                                       exist under Final_results_echotrace/

Re-run the binary analysis against the sysroot with:

  EGALITO_SYSROOT=$(pwd)/artifacts/all-running-containers/debug-symbols \\
    bash scripts/run_analysis.sh ...
"""

from __future__ import annotations

import concurrent.futures
import io
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import threading
from collections import defaultdict
from pathlib import Path


CONTAINERS = [
    "et_cassandra_3.0.29",
    "et_cassandra_5.0.6-bookworm",
    "et_elasticsearch_7.1.0",
    "et_elasticsearch_7.5.2",
    "et_groovy_4.0.0",
    "et_groovy_latest",
    "et_jetty_9.4.51",
    "et_jetty_latest",
    "et_jruby_9.4.2.0",
    "et_jruby_latest",
    "et_orientdb_3.2.19",
    "et_orientdb_latest",
    "et_solr_8.7.0",
    "et_solr_slim",
    "et_storm-2.4.0-temurin8_latest",
    "et_storm_2.4.0",
    "et_tomcat_11.0.18-jdk25-temurin",
    "et_tomcat_7.0",
    "et_zookeeper_3.4.14",
]
DEFAULT_DEBUGINFOD_URLS = " ".join(
    (
        "https://debuginfod.ubuntu.com",
        "https://debuginfod.debian.net",
        "https://debuginfod.fedoraproject.org",
        "https://debuginfod.centos.org",
        "https://debuginfod.rockylinux.org",
        "https://debuginfod.opensuse.org",
        "https://debuginfod.elfutils.org",
    )
)
BUILD_ID_RE = re.compile(r"Build ID:\s*([0-9a-fA-F]+)")
PRINT_LOCK = threading.Lock()
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
INSTALLER = SCRIPT_DIR / "install_container_dbgsym.sh"


def command_output(argv: list[str], **kwargs) -> str:
    result = subprocess.run(argv, check=True, text=True, capture_output=True, **kwargs)
    return result.stdout.strip()


def get_build_id(binary: Path) -> str | None:
    try:
        output = command_output(["readelf", "-n", str(binary)])
    except subprocess.CalledProcessError:
        return None
    match = BUILD_ID_RE.search(output)
    return match.group(1).lower() if match else None


def image_for(container: str) -> str:
    return command_output(
        ["docker", "inspect", "--format", "{{.Config.Image}}", container]
    )


def scan_container(container: str, image: str, temp_dir: Path) -> list[tuple[str, int, str]]:
    """Return (container path, byte size, GNU Build ID or empty) for ELF files."""
    print(f"[{container}] streaming rootfs export for ELF files...", flush=True)
    process = subprocess.Popen(
        ["docker", "export", container], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    assert process.stdout is not None
    found = []
    try:
        with tarfile.open(fileobj=process.stdout, mode="r|*") as archive:
            for member in archive:
                if not member.isfile() or member.size < 4:
                    continue
                contents = archive.extractfile(member)
                if contents is None:
                    continue
                magic = contents.read(4)
                if magic != b"\x7fELF":
                    continue
                temp_binary = temp_dir / "scan-elf"
                with temp_binary.open("wb") as output:
                    output.write(magic)
                    shutil.copyfileobj(contents, output, length=1024 * 1024)
                build_id = get_build_id(temp_binary) or ""
                found.append((member.name, member.size, build_id))
                if len(found) % 100 == 0:
                    print(f"[{container}] scanned {len(found)} ELF files...", flush=True)
        stderr = process.stderr.read().decode("utf-8", "replace") if process.stderr else ""
        status = process.wait()
        if status:
            raise RuntimeError(f"docker export exited {status}: {stderr.strip()}")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
    print(f"[{container}] found {len(found)} ELF files", flush=True)
    return found


def verify_debug_file(path: Path, build_id: str) -> bool:
    return get_build_id(path) == build_id


def existing_symbol(build_id: str, pool: Path) -> Path | None:
    pooled = pool / "build-id" / f"{build_id}.debug"
    candidates = [pooled]
    candidates.extend(Path("artifacts").glob(f"*/debug-symbols/build-id/{build_id}.debug"))
    for candidate in candidates:
        if candidate.is_file() and verify_debug_file(candidate, build_id):
            return candidate
    return None


def download_one(build_id: str, pool: Path, env: dict[str, str], index: int, total: int):
    target = pool / "build-id" / f"{build_id}.debug"
    prior = existing_symbol(build_id, pool)
    if prior:
        if prior != target:
            shutil.copy2(prior, target)
        return build_id, "REUSED", str(target)
    try:
        result = subprocess.run(
            ["debuginfod-find", "debuginfo", build_id],
            check=True,
            text=True,
            capture_output=True,
            env=env,
            timeout=240,
        )
        source = Path(result.stdout.strip())
        if not source.is_file() or not verify_debug_file(source, build_id):
            return build_id, "ID_MISMATCH", result.stdout.strip() or result.stderr.strip()
        shutil.copy2(source, target)
        with PRINT_LOCK:
            print(f"[{index}/{total}] fetched {build_id}", flush=True)
        return build_id, "DOWNLOADED", str(target)
    except subprocess.TimeoutExpired:
        return build_id, "TIMEOUT", "debuginfod-find exceeded 240 seconds"
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or "not found by configured debuginfod servers").strip()
        return build_id, "NOT_FOUND", message[-500:]


def container_install_fallback(
    container: str,
    missing_paths: list[str],
    expected_ids: set[str],
    pool: Path,
) -> tuple[dict[str, tuple[str, str]], str]:
    """Run install_container_dbgsym.sh inside `container`, extract matching
    .debug files, pool the ones whose Build ID still verifies.

    Returns ({build_id: (status, detail)}, diagnostics_tail) for only the IDs
    that were successfully resolved here. Callers merge it into the global map.
    """
    results: dict[str, tuple[str, str]] = {}
    if not missing_paths:
        return results, ""
    if not INSTALLER.is_file():
        return results, f"installer not found at {INSTALLER}"

    # Write the list of libraries we want package coverage for, then stage it
    # and the installer inside the container under /tmp. /tmp is world-writable
    # on every image we target; bind-mounting would be faster but needs the
    # container to be recreated, which we're explicitly avoiding.
    with tempfile.NamedTemporaryFile(
        "w", prefix="target-libs-", suffix=".txt", delete=False
    ) as handle:
        handle.write("\n".join(missing_paths) + "\n")
        libs_list = Path(handle.name)
    try:
        for src, dst in (
            (str(INSTALLER), f"{container}:/tmp/install_container_dbgsym.sh"),
            (str(libs_list), f"{container}:/tmp/target-libs.txt"),
        ):
            copy = subprocess.run(
                ["docker", "cp", src, dst],
                text=True,
                capture_output=True,
            )
            if copy.returncode != 0:
                return results, f"docker cp failed: {copy.stderr.strip()[-400:]}"

        print(
            f"[{container}] running dbgsym installer for {len(missing_paths)} lib(s)...",
            flush=True,
        )
        exec_proc = subprocess.run(
            ["docker", "exec", "-i", container, "sh", "/tmp/install_container_dbgsym.sh"],
            capture_output=True,
            timeout=1800,
        )
        diagnostics = exec_proc.stderr.decode("utf-8", "replace")
        if exec_proc.returncode != 0:
            return results, (
                f"installer exited {exec_proc.returncode}: "
                f"{diagnostics.strip()[-400:]}"
            )

        tar_bytes = exec_proc.stdout
        if not tar_bytes:
            return results, "installer produced no tar output: " + diagnostics.strip()[-300:]

        # The tar contains a `.build-id/XX/YYYYY.debug` tree. We only extract
        # entries whose reconstructed Build ID is still one we're looking for;
        # everything else (irrelevant dbg files the install step pulled in as
        # a side effect) is ignored.
        with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:") as archive:
            for member in archive:
                if not member.isfile():
                    continue
                parts = Path(member.name).parts
                try:
                    bid_dir_idx = parts.index(".build-id")
                except ValueError:
                    continue
                if len(parts) < bid_dir_idx + 3:
                    continue
                prefix = parts[bid_dir_idx + 1]
                tail = parts[bid_dir_idx + 2]
                if not tail.endswith(".debug"):
                    continue
                reconstructed = (prefix + tail[: -len(".debug")]).lower()
                if reconstructed not in expected_ids:
                    continue
                buf = archive.extractfile(member)
                if buf is None:
                    continue
                target = pool / "build-id" / f"{reconstructed}.debug"
                with target.open("wb") as fh:
                    shutil.copyfileobj(buf, fh)
                if not verify_debug_file(target, reconstructed):
                    target.unlink(missing_ok=True)
                    results[reconstructed] = (
                        "CONTAINER_ID_MISMATCH",
                        f"installed .debug in {container} did not match Build ID",
                    )
                    continue
                results[reconstructed] = ("CONTAINER_INSTALL", str(target))
                with PRINT_LOCK:
                    print(f"[{container}] installed {reconstructed}", flush=True)
        return results, diagnostics.strip()[-400:]
    except subprocess.TimeoutExpired:
        return results, "docker exec installer exceeded 1800 seconds"
    finally:
        libs_list.unlink(missing_ok=True)


def materialize_sysroot(pool: Path, build_ids: list[str]) -> int:
    """Create egalito-friendly `/usr/lib/debug/.build-id/XX/YY.debug` symlinks
    for every Build ID that has a verified .debug in the pool. Returns the
    count of symlinks that ended up present.
    """
    debug_root = pool / "usr" / "lib" / "debug" / ".build-id"
    count = 0
    for build_id in build_ids:
        src = pool / "build-id" / f"{build_id}.debug"
        if not src.is_file():
            continue
        subdir = debug_root / build_id[:2]
        subdir.mkdir(parents=True, exist_ok=True)
        link = subdir / f"{build_id[2:]}.debug"
        # Relative target so the sysroot tree is relocatable.
        relative = Path(os.path.relpath(src, subdir))
        if link.is_symlink() or link.exists():
            try:
                if link.is_symlink() and Path(os.readlink(link)) == relative:
                    count += 1
                    continue
            except OSError:
                pass
            link.unlink()
        link.symlink_to(relative)
        count += 1
    return count


def write_tsv(path: Path, header: tuple[str, ...], rows: list[tuple[str, ...]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output:
        output.write("\t".join(header) + "\n")
        for row in rows:
            output.write("\t".join(cell.replace("\t", " ").replace("\n", " ") for cell in row) + "\n")


def write_missing_by_target(
    pool: Path,
    inventory: list[tuple[str, str, str, int, str]],
    statuses: dict[str, tuple[str, str]],
    targets_root: Path,
) -> list[str]:
    """One .tsv per target that exists under Final_results_echotrace/, listing
    libs whose Build ID is still unresolved. The container name is
    `et_<target>` by convention; targets without that mapping are skipped.
    """
    if not targets_root.is_dir():
        return []
    target_names = sorted(p.name for p in targets_root.iterdir() if p.is_dir())
    reports_dir = pool / "missing_by_target"
    written: list[str] = []
    for target in target_names:
        container = f"et_{target}"
        rows: list[tuple[str, ...]] = []
        for ct, image, path, size, build_id in inventory:
            if ct != container:
                continue
            if not build_id:
                rows.append((path, "", str(size), image, "NO_GNU_BUILD_ID", ""))
                continue
            status, detail = statuses.get(build_id, ("UNKNOWN", ""))
            if status in {"DOWNLOADED", "REUSED", "CONTAINER_INSTALL"}:
                continue
            rows.append((path, build_id, str(size), image, status, detail))
        # Always emit the file, even when empty — "no missing libs" is useful
        # feedback for the re-run operator.
        write_tsv(
            reports_dir / f"{target}.tsv",
            ("path", "gnu_build_id", "size_bytes", "image", "status", "detail"),
            rows,
        )
        written.append(target)
    return written


def main() -> int:
    for tool in ("docker", "readelf", "debuginfod-find"):
        if shutil.which(tool) is None:
            raise SystemExit(f"{tool} must be installed")

    root = Path("artifacts/all-running-containers/debug-symbols")
    root.mkdir(parents=True, exist_ok=True)
    (root / "build-id").mkdir(exist_ok=True)
    env = os.environ.copy()
    if not env.get("DEBUGINFOD_URLS"):
        env["DEBUGINFOD_URLS"] = DEFAULT_DEBUGINFOD_URLS

    # ---------------------------------------------------------------- inventory
    # ECHOTRACE_CONTAINERS=a,b,c scopes a run to a subset of CONTAINERS. Used
    # for dry-runs and for re-trying a single container after a transient
    # debuginfod/apt failure without rescanning every rootfs.
    containers_env = env.get("ECHOTRACE_CONTAINERS", "").strip()
    if containers_env:
        wanted = {c.strip() for c in containers_env.split(",") if c.strip()}
        containers_list = [c for c in CONTAINERS if c in wanted]
        missing_filter = wanted - set(CONTAINERS)
        if missing_filter:
            print(
                f"Warning: unknown containers in ECHOTRACE_CONTAINERS: "
                f"{', '.join(sorted(missing_filter))}",
                flush=True,
            )
        if not containers_list:
            raise SystemExit("ECHOTRACE_CONTAINERS matched no known containers")
    else:
        containers_list = CONTAINERS

    inventory: list[tuple[str, str, str, int, str]] = []
    for container in containers_list:
        try:
            image = image_for(container)
        except subprocess.CalledProcessError as exc:
            print(
                f"[{container}] skipping: docker inspect failed "
                f"({exc.stderr.strip() if exc.stderr else exc})",
                flush=True,
            )
            continue
        with tempfile.TemporaryDirectory(prefix="echotrace-elf-scan-") as work:
            try:
                records = scan_container(container, image, Path(work))
            except Exception as exc:
                print(f"[{container}] scan failed: {exc}", flush=True)
                continue
        inventory.extend(
            (container, image, path, size, build_id) for path, size, build_id in records
        )

    ids = sorted({row[4] for row in inventory if row[4]})
    print(
        f"Inventory complete: {len(inventory)} ELF paths, {len(ids)} unique GNU Build IDs",
        flush=True,
    )

    # ------------------------------------------------------------- debuginfod
    statuses: dict[str, tuple[str, str]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(download_one, build_id, root, env, i, len(ids)): build_id
            for i, build_id in enumerate(ids, 1)
        }
        for future in concurrent.futures.as_completed(futures):
            build_id, status, detail = future.result()
            statuses[build_id] = (status, detail)

    resolved = {"DOWNLOADED", "REUSED"}
    unresolved_ids = {bid for bid, (status, _) in statuses.items() if status not in resolved}
    print(
        f"debuginfod stage: {len(ids) - len(unresolved_ids)}/{len(ids)} resolved; "
        f"{len(unresolved_ids)} still missing",
        flush=True,
    )

    # ---------------------------------- container-side install fallback (B)
    #
    # Group missing IDs by container. If a Build ID appears in multiple
    # containers we try each container until one succeeds; stopping early keeps
    # install-time cost proportional to the number of distinct misses, not to
    # the cross product.
    by_container: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for container, _image, path, _size, build_id in inventory:
        if build_id in unresolved_ids:
            by_container[container][build_id].append(path)

    for container, id_to_paths in by_container.items():
        still_missing = [bid for bid in id_to_paths if bid in unresolved_ids]
        if not still_missing:
            continue
        paths = sorted({p for bid in still_missing for p in id_to_paths[bid]})
        resolved_here, diagnostics = container_install_fallback(
            container, paths, set(still_missing), root
        )
        for build_id, (status, detail) in resolved_here.items():
            statuses[build_id] = (status, detail)
            if status == "CONTAINER_INSTALL":
                unresolved_ids.discard(build_id)
        if diagnostics:
            # Keep container diagnostics terse — the installer already logs
            # structured lines on stderr. Stashing them alongside the manifest
            # is more useful than dumping into the top-level log.
            diag_path = root / "container_diagnostics" / f"{container}.log"
            diag_path.parent.mkdir(parents=True, exist_ok=True)
            diag_path.write_text(diagnostics + "\n", encoding="utf-8")

    # --------------------------------------------- sysroot symlink layout (A)
    linked = materialize_sysroot(root, ids)

    # -------------------------------------------------------- global manifests
    inventory_rows = []
    for container, image, path, size, build_id in inventory:
        status, symbol_path = statuses.get(build_id, ("NO_GNU_BUILD_ID", ""))
        inventory_rows.append(
            (container, image, path, str(size), build_id, status, symbol_path)
        )
    write_tsv(
        root / "elf_inventory.tsv",
        ("container", "image", "path", "size_bytes", "gnu_build_id", "symbol_status", "debug_file"),
        inventory_rows,
    )
    write_tsv(
        root / "symbol_manifest.tsv",
        ("gnu_build_id", "status", "debug_file_or_error"),
        [(build_id, *statuses[build_id]) for build_id in ids],
    )

    # --------------------------------------------------- per-target reports (C)
    targets_root = PROJECT_ROOT / "Final_results_echotrace"
    reported = write_missing_by_target(root, inventory, statuses, targets_root)

    # --------------------------------------------------------------- summary
    missing_after_b = sum(
        1 for status, _ in statuses.values()
        if status not in {"DOWNLOADED", "REUSED", "CONTAINER_INSTALL"}
    )
    no_build_id = sum(not row[4] for row in inventory)
    print(
        f"Done: {len(ids) - missing_after_b}/{len(ids)} Build IDs resolved; "
        f"{missing_after_b} still unresolved; "
        f"{no_build_id} ELF paths have no GNU Build ID.",
        flush=True,
    )
    print(f"Sysroot symlinks ({linked}) under {root / 'usr/lib/debug/.build-id'}", flush=True)
    if reported:
        print(
            f"Per-target reports under {root / 'missing_by_target'}: "
            f"{', '.join(reported)}",
            flush=True,
        )
    print(f"Artifacts: {root.resolve()}", flush=True)
    return 0 if not missing_after_b else 2


if __name__ == "__main__":
    raise SystemExit(main())
