#!/usr/bin/env python3
"""Give the stripped ELFs of an analysed target their symbol tables back.

SysPart names a function only when the ELF carries a .symtab; for stripped
container binaries and libraries it falls back to `fuzzyfunc-0x<addr>`, so the
call graphs in Final_results_echotrace/<target>/Binary_Analysis lose their
function names. This script works on the extracted dataset of each target
rather than on the live container rootfs, so it only fetches what the analysis
actually loads:

  1. Inventory every ELF under Dataset/{LIBS_,BINARIES_}<target>/ and record
     its GNU Build ID and whether it is stripped. Some dataset copies are
     truncated (their section headers lie past EOF, so SysPart cannot load
     them); those are re-copied from the running `et_<target>` container,
     matched by Build ID, which survives because the note is at the start.
  2. For each stripped Build ID, reuse a verified .debug from the shared pool,
     else ask debuginfod, else download the exact-version dbgsym/dbg package
     from the distro archive (snapshot.debian.org, Launchpad, CentOS
     debuginfo). The owning package and version are read from the running
     `et_<target>` container with dpkg-query/rpm; nothing is installed in it.
     Optionally (CONTAINER_FALLBACK=1) the remaining IDs are installed inside
     the container with install_container_dbgsym.sh, which modifies it.
  3. Copy the dataset to Dataset_symbolized/ and, for every stripped ELF whose
     .debug was found, merge the debug file back in with eu-unstrip and drop
     the DWARF again with `objcopy --strip-debug`. The result is the original
     code with a restored .symtab, small enough for SysPart to load quickly.
     The original Dataset/ is never modified.

Usage:
  python3 scripts/symbolize_dataset.py                 # every target
  python3 scripts/symbolize_dataset.py storm_2.4.0 ... # a subset

  RESULTS_ROOT=<dir> reads and writes targets there instead of
  Final_results_echotrace/ in this repository.

  CONTAINER_FALLBACK=1 additionally apt/dnf-installs dbgsym packages inside
  the containers for whatever the archives did not provide.

Outputs, per target:
  Dataset_symbolized/                 dataset copy with symbols restored
  Dataset_symbolized/symbols.tsv      per-ELF Build ID, status and debug file
"""

from __future__ import annotations

import concurrent.futures
import gzip
import hashlib
import json
import lzma
import os
import re
import shutil
import struct
import tempfile
import time
import urllib.parse
import zipfile
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from download_container_debug_symbols import (  # noqa: E402
    DEFAULT_DEBUGINFOD_URLS,
    container_install_fallback,
    download_one,
    get_build_id,
    write_tsv,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_ROOT = Path(os.environ.get("RESULTS_ROOT", PROJECT_ROOT / "Final_results_echotrace"))
POOL = PROJECT_ROOT / "artifacts" / "all-running-containers" / "debug-symbols"
RESOLVED = {"DOWNLOADED", "REUSED", "PACKAGE_ARCHIVE", "CONTAINER_INSTALL"}
REPLACED: dict[tuple[str, str], str] = {}  # wrong-platform copy swapped for the x86-64 JAR build
ADDED: dict[tuple[str, str], str] = {}     # missing dependency copied from the container


def is_elf(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(4) == b"\x7fELF"
    except OSError:
        return False


def is_truncated(path: Path) -> bool:
    with path.open("rb") as handle:
        header = handle.read(64)
    if len(header) < 64 or header[4] != 2:  # ELFCLASS64 only
        return False
    shoff, = struct.unpack_from("<Q", header, 0x28)
    shentsize, shnum = struct.unpack_from("<HH", header, 0x3A)
    return shoff + shentsize * shnum > path.stat().st_size


def is_intact_original(candidate: Path, truncated: Path) -> bool:
    """A truncated copy is a byte prefix of its original. Comparing the prefix
    also works for ELFs without a GNU Build ID (Temurin's libjvm.so)."""
    if is_truncated(candidate):
        return False
    size = truncated.stat().st_size
    if candidate.stat().st_size <= size:
        return False
    with truncated.open("rb") as short, candidate.open("rb") as full:
        while True:
            chunk = short.read(1 << 20)
            if not chunk:
                return True
            if full.read(len(chunk)) != chunk:
                return False


def recover_from_container(container: str, name: str, truncated: Path, dest: Path) -> str:
    """Copy the intact original of `truncated` out of `container` over `dest`.
    JVM-extracted libraries carry a random numeric suffix that differs per
    run (librocksdbjni1022...so), so long digit runs are wildcarded."""
    pattern = re.sub(r"\d{6,}", "*", name)
    found = subprocess.run(
        ["docker", "exec", container, "sh", "-c", f"find / -xdev -name '{pattern}' 2>/dev/null"],
        text=True, capture_output=True, timeout=600,
    ).stdout.split()
    with tempfile.TemporaryDirectory(prefix="echotrace-recover-") as work:
        for index, path in enumerate(found):
            candidate = Path(work) / str(index)
            if subprocess.run(["docker", "cp", "-L", f"{container}:{path}", str(candidate)],
                              capture_output=True).returncode != 0 or not candidate.is_file():
                continue
            if is_intact_original(candidate, truncated):
                shutil.copy2(candidate, dest)
                return path
    return ""


def recover_locally(target: str, name: str, truncated: Path, dest: Path) -> str:
    """Fallbacks for truncated files the container no longer holds: binaries
    the host ran on the container's behalf (runc), and JNI libraries the JVM
    unpacked from a JAR into a since-deleted temp file. The dataset JARs can be
    truncated too, so JARs are copied out of the container."""
    for directory in ("/usr/bin", "/usr/sbin", "/bin", "/sbin"):
        host = Path(directory) / name
        if host.is_file() and is_intact_original(host, truncated):
            shutil.copy2(host, dest)
            return str(host)
    # Names the member may have inside its JAR: the random-suffix form
    # (librocksdbjni1022....so -> librocksdbjni*) and the <lib>_<jar>.so form
    # the extraction step writes (libzstd-jni-1.5.7-2_zstd-jni-1.5.7-2.so).
    prefix = re.sub(r"\d{6,}.*$", "", name)
    stems = {prefix} if prefix != name else set()
    if "_" in name:
        stems.add(name.split("_", 1)[0])
    if not stems:
        stems.add(name.removesuffix(".so"))
    for jar_path, archive in container_jars(f"et_{target}"):
        for member in archive.namelist():
            base = Path(member).name
            if ".so" not in base or not any(base.startswith(stem) for stem in stems):
                continue
            with tempfile.TemporaryDirectory(prefix="echotrace-recover-") as work:
                try:
                    candidate = Path(archive.extract(member, work))
                except (zipfile.BadZipFile, OSError):
                    continue
                if is_intact_original(candidate, truncated):
                    shutil.copy2(candidate, dest)
                    return f"et_{target}:{jar_path}!/{member}"
    return ""


JAR_CACHE: dict[str, list[tuple[str, zipfile.ZipFile]]] = {}
JAR_WORK = tempfile.TemporaryDirectory(prefix="echotrace-jars-")


def container_jars(container: str) -> list[tuple[str, zipfile.ZipFile]]:
    """Every JAR in `container` that contains a native library, copied out
    once per run as a single tar stream and kept open for later lookups."""
    if container in JAR_CACHE:
        return JAR_CACHE[container]
    paths = subprocess.run(
        ["docker", "exec", container, "sh", "-c", "find / -xdev -name '*.jar' -type f 2>/dev/null"],
        text=True, capture_output=True, timeout=600,
    ).stdout.split()
    root = Path(JAR_WORK.name) / container
    root.mkdir(parents=True, exist_ok=True)
    if paths:
        tar = subprocess.run(["docker", "exec", "-i", container, "tar", "-C", "/", "-cf", "-", "-T", "-"],
                             input="\n".join(p.lstrip("/") for p in paths).encode() + b"\n",
                             capture_output=True)
        subprocess.run(["tar", "-C", str(root), "-xf", "-"], input=tar.stdout, capture_output=True)
    found = []
    for path in paths:
        try:
            archive = zipfile.ZipFile(root / path.lstrip("/"))
        except (zipfile.BadZipFile, OSError):
            continue
        if any(".so" in Path(m).name for m in archive.namelist()):
            found.append((path, archive))
        else:
            archive.close()
    JAR_CACHE[container] = found
    print(f"[{container}] indexed {len(found)} JARs with native libraries", flush=True)
    return found


def http_get(url: str, dest: Path | None = None, tries: int = 4) -> bytes | None:
    """snapshot.debian.org routinely answers 503/504 under load; retry."""
    for attempt in range(tries):
        argv = ["curl", "-sfL", "--max-time", "600", url]
        if dest is not None:
            argv[1:1] = ["-o", str(dest)]
        result = subprocess.run(argv, capture_output=True)
        if result.returncode == 0:
            return result.stdout if dest is None else b"ok"
        if result.returncode == 22 and b"404" in result.stderr:
            return None
        time.sleep(5 * (attempt + 1))
    return None


def package_owners(container: str, paths: list[str]) -> list[tuple[str, str, str, str]]:
    """(distro, package, version, source package) for each path, read-only."""
    script = r"""
. /etc/os-release
for p in "$@"; do
  r=$(readlink -f "$p")
  if command -v dpkg-query >/dev/null 2>&1; then
    pkg=""
    # merged-/usr images: dpkg records /lib/... while find reports /usr/lib/...
    for q in "$r" "$p" "${r#/usr}" "${p#/usr}"; do
      [ -n "$pkg" ] && break
      pkg=$(dpkg-query -S "$q" 2>/dev/null | head -n1 | cut -d: -f1)
    done
    [ -n "$pkg" ] && dpkg-query -W -f="$ID\t\${Package}\t\${Version}\t\${source:Package}\n" "$pkg" 2>/dev/null | head -n1
  elif command -v rpm >/dev/null 2>&1; then
    rpm -qf --qf "$ID\t%{NAME}\t%{VERSION}-%{RELEASE}.%{ARCH}\t%{SOURCERPM}\n" "$r" 2>/dev/null | head -n1
  fi
done
"""
    result = subprocess.run(["docker", "exec", container, "sh", "-c", script, "sh", *paths],
                            text=True, capture_output=True, timeout=600)
    owners = set()
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) == 4 and all(parts):
            owners.add(tuple(parts))
    return sorted(owners)


def package_urls(distro: str, package: str, version: str, source: str) -> list[str]:
    """Candidate download URLs for the debug package matching `version`."""
    if distro in {"centos", "rhel", "rocky", "almalinux"}:
        source_name = re.sub(r"-[^-]+-[^-]+\.src\.rpm$", "", source)
        major = "7" if ".el7" in version else "8" if ".el8" in version else ""
        return [f"http://debuginfo.centos.org/{major}/x86_64/{source_name}-debuginfo-{version}.rpm"] if major else []
    names = [f"{package}-dbgsym", f"{package}-dbg"]
    if source == "glibc":
        names.append("libc6-dbg")
    plain_version = version.split(":", 1)[-1]
    urls = []
    for name in dict.fromkeys(names):
        if distro == "ubuntu":
            for ext in ("ddeb", "deb"):
                urls.append(f"https://launchpad.net/ubuntu/+archive/primary/+files/{name}_{plain_version}_amd64.{ext}")
        elif distro == "debian":
            # Debian's own pools first: archive.debian.org keeps the debug
            # archive of end-of-life releases (buster-debug) and deb.debian.org
            # the current ones; -dbg packages live in the regular archive.
            # snapshot.debian.org is the fallback and is often slow or down.
            pool = source[:4] if source.startswith("lib") else source[:1]
            deb = f"{pool}/{source}/{name}_{plain_version}_amd64.deb"
            for archive in ("https://deb.debian.org/debian-debug", "http://archive.debian.org/debian-debug",
                            "https://deb.debian.org/debian", "http://archive.debian.org/debian"):
                urls.append(f"{archive}/pool/main/{deb}")
            for archive in ("https://deb.debian.org/debian-security-debug", "http://archive.debian.org/debian-security-debug"):
                urls.append(f"{archive}/pool/updates/main/{deb}")
            urls.append(f"snapshot:{name}/{version}")
    return urls


def resolve_snapshot(spec: str) -> str | None:
    name, version = spec.removeprefix("snapshot:").split("/", 1)
    body = http_get(f"https://snapshot.debian.org/mr/binary/{urllib.parse.quote(name)}/"
                    f"{urllib.parse.quote(version, safe='')}/binfiles?fileinfo=1")
    if not body:
        return None
    try:
        info = json.loads(body)
    except ValueError:
        return None
    for digest, files in info.get("fileinfo", {}).items():
        if any(f["name"].endswith("_amd64.deb") for f in files):
            return f"https://snapshot.debian.org/file/{digest}"
    return None


def rpm_payload(archive: Path) -> bytes:
    """The cpio payload of an RPM, without needing rpm2cpio on the host: the
    payload is the first xz/zstd/gzip stream after the headers."""
    data = archive.read_bytes()
    for magic, decompress in ((b"\xfd7zXZ\x00", lzma.decompress),
                              (b"\x28\xb5\x2f\xfd", None),
                              (b"\x1f\x8b\x08", gzip.decompress)):
        offset = data.find(magic, 96)
        if offset < 0:
            continue
        if decompress is None:
            return subprocess.run(["zstd", "-dc"], input=data[offset:], capture_output=True).stdout
        return decompress(data[offset:])
    return b""


def harvest_package(url: str, wanted: set[str], pool: Path) -> set[str]:
    """Download one debug package (cached under pool/packages) and copy every
    Build-ID-verified .debug it contains for an ID in `wanted` into the pool."""
    cache = pool / "packages"
    cache.mkdir(exist_ok=True)
    if url.startswith("snapshot:"):
        key = url.removeprefix("snapshot:").replace("/", "_") + ".deb"
        real = None
    else:
        key, real = url.rsplit("/", 1)[-1], url
    archive = cache / key
    # The same file is tried on several mirrors, so a miss is remembered per
    # URL; the downloaded package itself is shared under its file name.
    missing_marker = cache / (key + ".missing" if real is None
                              else f"{key}.{hashlib.sha1(url.encode()).hexdigest()[:10]}.missing")
    if missing_marker.exists():
        return set()
    if not archive.is_file():
        if real is None:
            real = resolve_snapshot(url)
        if real is None or http_get(real, archive) is None:
            archive.unlink(missing_ok=True)
            missing_marker.touch()
            return set()
    found = set()
    with tempfile.TemporaryDirectory(prefix="echotrace-pkg-") as work:
        if archive.suffix == ".rpm":
            extract = subprocess.run(["cpio", "-idm", "--quiet"], input=rpm_payload(archive),
                                     cwd=work, capture_output=True)
        else:
            extract = subprocess.run(["dpkg-deb", "-x", str(archive), work], capture_output=True)
        if extract.returncode != 0:
            return found
        for debug in Path(work).rglob("*.debug"):
            if not debug.is_file():
                continue
            build_id = get_build_id(debug)
            if build_id in wanted:
                # Package payloads are read-only and several packages can carry
                # the same Build ID; keep the first copy, writable.
                target = pool / "build-id" / f"{build_id}.debug"
                if not target.is_file():
                    shutil.copyfile(debug, target)
                    target.chmod(0o644)
                found.add(build_id)
    return found


FOREIGN_NEEDED = re.compile(r"^(libc\.so\.(?!6$)\d+|libm\.so\.(?!6$)\d+|libc\.musl.*|ld-musl.*)$")


def elf_machine_and_needed(path: Path) -> tuple[str, list[str]]:
    header = subprocess.run(["readelf", "-h", "-d", "-W", str(path)], text=True, capture_output=True).stdout
    machine = next((l.split(":", 1)[1].strip() for l in header.splitlines() if "Machine:" in l), "")
    needed = re.findall(r"\(NEEDED\)\s+Shared library: \[([^\]]+)\]", header)
    return machine, needed


def runnable_here(path: Path) -> bool:
    """x86-64 and linked against glibc, i.e. a build the container's JVM can
    actually have loaded. JAR bundles ship one build per platform and the
    extraction sometimes kept the wrong one (cassandra's libjnidispatch.so is
    i386, solr's libsnappyjava.so wants FreeBSD's libc.so.7)."""
    machine, needed = elf_machine_and_needed(path)
    return machine == "Advanced Micro Devices X86-64" and not any(FOREIGN_NEEDED.match(n) for n in needed)


def jar_stem(name: str) -> str:
    """librocksdbjni1022...so -> librocksdbjni, libzstd-jni-1.5.7-2_zstd-jni-1.5.7-2.so
    -> libzstd-jni-1.5.7-2, libsnappyjava.so -> libsnappyjava."""
    stem = re.sub(r"\d{6,}.*$", "", name)
    if stem == name:
        stem = name.split("_", 1)[0] if "_" in name else name
    return stem.removesuffix(".so")


def replace_platform_build(target: str, name: str, dest: Path) -> str:
    """Overwrite `dest` with the Linux x86-64 glibc build of the same JNI
    library from a JAR in the container."""
    stem = jar_stem(name)
    for jar_path, archive in container_jars(f"et_{target}"):
        for member in archive.namelist():
            lowered = member.lower()
            base = Path(member).name
            if not (base.startswith(stem) and base.endswith(".so")):
                continue
            if "linux" not in lowered or not re.search(r"x86[_-]64|amd64", lowered) or "musl" in lowered:
                continue
            with tempfile.TemporaryDirectory(prefix="echotrace-platform-") as work:
                try:
                    candidate = Path(archive.extract(member, work))
                except (zipfile.BadZipFile, OSError):
                    continue
                if runnable_here(candidate):
                    shutil.copyfile(candidate, dest)
                    return f"et_{target}:{jar_path}!/{member}"
    return ""


def complete_dependencies(target: str, out_root: Path) -> list[str]:
    """Copy DT_NEEDED libraries that the mirror lacks out of the container.
    Without them Egalito silently loads the host's copy (tomcat_7.0 had no
    container libc at all), so the call graph would describe the host."""
    libs = next(out_root.glob("LIBS_*"), None)
    if libs is None:
        return []
    deps_dir = libs / "_container_deps"
    container = f"et_{target}"
    added: list[str] = []
    for _ in range(4):  # dependencies of dependencies
        present = {p.name for p in out_root.rglob("*") if p.is_file() or p.is_symlink()}
        wanted: set[str] = set()
        for elf in out_root.rglob("*"):
            if elf.is_file() and not elf.is_symlink() and is_elf(elf):
                wanted.update(n for n in elf_machine_and_needed(elf)[1]
                              if n not in present and "/" not in n and not FOREIGN_NEEDED.match(n))
        if not wanted:
            break
        expr = " -o ".join(f"-name '{n}'" for n in sorted(wanted))
        found = subprocess.run(
            ["docker", "exec", container, "sh", "-c",
             f"find /lib /lib64 /usr/lib /usr/lib64 /usr/local/lib \\( {expr} \\) 2>/dev/null"],
            text=True, capture_output=True, timeout=600,
        ).stdout.split()
        progress = False
        for path in found:
            name = Path(path).name
            if name in present or name in added:
                continue
            deps_dir.mkdir(exist_ok=True)
            dest = deps_dir / name
            if subprocess.run(["docker", "cp", "-L", f"{container}:{path}", str(dest)],
                              capture_output=True).returncode == 0 and dest.is_file() and runnable_here(dest):
                added.append(name)
                progress = True
            else:
                dest.unlink(missing_ok=True)
        if not progress:
            break
    return added


def add_missing_binaries(target: str, out_root: Path) -> list[str]:
    """Binaries that Binary_Analysis/ has results for but the dataset lacks
    (tomcat_7.0's BINARIES_ folder is empty; its originals came from an older
    tree) are copied from the container, or for runc, the host runtime, from
    the host."""
    analysed = {d.name for d in (RESULTS_ROOT / target / "Binary_Analysis").glob("syscalls_BIN_*/*") if d.is_dir()}
    present = {p.name for p in out_root.glob("BINARIES_*/**/*") if p.is_file()}
    bins = out_root / f"BINARIES_{target}"
    bins.mkdir(exist_ok=True)
    added = []
    for name in sorted(analysed - present):
        dest = bins / name
        path = subprocess.run(["docker", "exec", f"et_{target}", "sh", "-c", f"command -v {name}"],
                              text=True, capture_output=True).stdout.strip()
        if path.startswith("/") and subprocess.run(
                ["docker", "cp", "-L", f"et_{target}:{path}", str(dest)], capture_output=True).returncode == 0:
            added.append((name, f"et_{target}:{path}"))
        elif shutil.which(name) and name == "runc":
            shutil.copy2(shutil.which(name), dest)
            added.append((name, f"host:{shutil.which(name)}"))
        if dest.is_file() and not is_elf(dest):
            dest.unlink()
            added.pop()
    return added


def has_symtab(path: Path) -> bool:
    result = subprocess.run(["readelf", "-S", "-W", str(path)], text=True, capture_output=True)
    return " .symtab " in result.stdout


def dataset_elfs(dataset: Path) -> list[Path]:
    elfs = []
    for sub in sorted(dataset.iterdir()):
        if not sub.is_dir() or not sub.name.startswith(("LIBS_", "BINARIES_")):
            continue
        elfs.extend(p for p in sorted(sub.rglob("*")) if p.is_file() and not p.is_symlink() and is_elf(p))
    return elfs


def sibling_containers(target: str) -> list[str]:
    """et_<target> first, then other running et_<app>* containers. Some
    datasets mix artifacts from variants of the same application image (the
    storm_2.4.0 binaries partly come from et_storm-2.4.0-temurin8_latest);
    every .debug is still verified against the expected Build ID."""
    primary = f"et_{target}"
    app = re.split(r"[_-]", target, maxsplit=1)[0]
    running = subprocess.run(["docker", "ps", "--format", "{{.Names}}"],
                             text=True, capture_output=True).stdout.split()
    return [primary] + sorted(n for n in running if n != primary and n.startswith(f"et_{app}"))


def container_paths(container: str, names: set[str]) -> list[str]:
    """Absolute paths inside `container` of regular files named in `names`.
    Extraction flattens the container layout, so the original path has to be
    looked up again for the package manager to find the owner."""
    if not names:
        return []
    expr = " -o ".join(f"-name '{n}'" for n in sorted(names))
    result = subprocess.run(
        ["docker", "exec", container, "sh", "-c",
         f"find / -xdev \\( {expr} \\) -type f 2>/dev/null"],
        text=True, capture_output=True, timeout=600,
    )
    return sorted({line for line in result.stdout.splitlines() if line.startswith("/")})


def symbolize(stripped: Path, debug: Path, out: Path) -> str:
    merged = out.with_name(out.name + ".unstrip")
    try:
        subprocess.run(["eu-unstrip", "-o", str(merged), str(stripped), str(debug)],
                       check=True, text=True, capture_output=True)
        subprocess.run(["objcopy", "--strip-debug", str(merged), str(out)],
                       check=True, text=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        return (exc.stderr or exc.stdout or "failed").strip()[-300:]
    finally:
        merged.unlink(missing_ok=True)
    shutil.copymode(stripped, out)
    return ""


def main(argv: list[str]) -> int:
    for tool in ("readelf", "eu-unstrip", "objcopy", "debuginfod-find"):
        if shutil.which(tool) is None:
            raise SystemExit(f"{tool} must be installed")

    targets = argv or sorted(p.name for p in RESULTS_ROOT.iterdir() if (p / "Dataset").is_dir())
    (POOL / "build-id").mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.setdefault("DEBUGINFOD_URLS", DEFAULT_DEBUGINFOD_URLS)

    # ---------------------------------------------------------------- inventory
    # (target, path relative to Dataset/, Build ID, stripped, truncated)
    inventory: list[tuple[str, Path, str, bool, bool]] = []
    for target in targets:
        dataset = RESULTS_ROOT / target / "Dataset"
        out_root = RESULTS_ROOT / target / "Dataset_symbolized"
        if out_root.exists():
            shutil.rmtree(out_root)
        out_root.mkdir()
        for sub in sorted(dataset.iterdir()):
            if sub.is_dir() and sub.name.startswith(("LIBS_", "BINARIES_")):
                shutil.copytree(sub, out_root / sub.name, symlinks=True)
        for elf in dataset_elfs(dataset):
            rel = elf.relative_to(dataset)
            truncated = is_truncated(elf)
            if truncated:
                origin = (recover_from_container(f"et_{target}", rel.name, elf, out_root / rel)
                          or recover_locally(target, rel.name, elf, out_root / rel))
                if origin:
                    truncated = False
                    print(f"[{target}] recovered truncated {rel} from {origin}", flush=True)
                else:
                    print(f"[{target}] could not recover truncated {rel}", flush=True)
            work = out_root / rel
            if (truncated or not runnable_here(work)) and rel.parts[0].startswith("LIBS_"):
                origin = replace_platform_build(target, rel.name, work)
                if origin:
                    truncated = False
                    REPLACED[(target, str(rel))] = origin
                    print(f"[{target}] replaced {rel} with {origin}", flush=True)
            # Build ID and strip status come from the (possibly replaced) copy.
            inventory.append((target, rel, get_build_id(work) or "", not has_symtab(work), truncated))
        for name, origin in add_missing_binaries(target, out_root):
            rel = Path(f"BINARIES_{target}") / name
            ADDED[(target, str(rel))] = origin
            inventory.append((target, rel, get_build_id(out_root / rel) or "", not has_symtab(out_root / rel), False))
            print(f"[{target}] added missing binary {name} from {origin}", flush=True)
        for name in complete_dependencies(target, out_root):
            rel = next(p for p in out_root.glob(f"LIBS_*/_container_deps/{name}")).relative_to(out_root)
            ADDED[(target, str(rel))] = f"et_{target} (missing DT_NEEDED)"
            inventory.append((target, rel, get_build_id(out_root / rel) or "", not has_symtab(out_root / rel), False))
        print(f"[{target}] inventoried", flush=True)

    wanted = sorted({bid for _, _, bid, stripped, _ in inventory if stripped and bid})
    print(f"{len(inventory)} ELFs, {len(wanted)} stripped Build IDs to resolve", flush=True)

    # ------------------------------------------------------------- debuginfod
    statuses: dict[str, tuple[str, str]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(download_one, bid, POOL, env, i, len(wanted))
                   for i, bid in enumerate(wanted, 1)]
        for future in concurrent.futures.as_completed(futures):
            bid, status, detail = future.result()
            statuses[bid] = (status, detail)
    missing = {bid for bid in wanted if statuses[bid][0] not in RESOLVED}
    print(f"debuginfod: {len(wanted) - len(missing)}/{len(wanted)} resolved", flush=True)

    # ------------------------------------------------ distro package archives
    def missing_by_target() -> dict[str, dict[str, set[str]]]:
        grouped: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        for target, rel, bid, _, _ in inventory:
            if bid in missing:
                grouped[target][bid].add(rel.name)
        return grouped

    if missing:
        urls: set[str] = set()
        for target, id_to_names in missing_by_target().items():
            names = {n for ids in id_to_names.values() for n in ids}
            for container in sibling_containers(target):
                try:
                    owners = package_owners(container, container_paths(container, names))
                except (subprocess.SubprocessError, OSError) as exc:
                    print(f"[{container}] package lookup failed: {exc}", flush=True)
                    continue
                for owner in owners:
                    urls.update(package_urls(*owner))
                print(f"[{container}] {len(owners)} owning packages", flush=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            for found in executor.map(lambda url: harvest_package(url, set(missing), POOL), sorted(urls)):
                for bid in found:
                    statuses[bid] = ("PACKAGE_ARCHIVE", str(POOL / "build-id" / f"{bid}.debug"))
                    missing.discard(bid)
        print(f"after package archives: {len(wanted) - len(missing)}/{len(wanted)} resolved", flush=True)

    # ---------------------------------------- in-container package fallback
    if missing and os.environ.get("CONTAINER_FALLBACK") == "1":
        for target, id_to_names in missing_by_target().items():
            still = {bid for bid in id_to_names if bid in missing}
            if not still:
                continue
            container = f"et_{target}"
            try:
                paths = container_paths(container, {n for bid in still for n in id_to_names[bid]})
            except (subprocess.SubprocessError, OSError) as exc:
                print(f"[{container}] lookup failed: {exc}", flush=True)
                continue
            if not paths:
                print(f"[{container}] none of the missing files found in the container", flush=True)
                continue
            resolved, diagnostics = container_install_fallback(container, paths, still, POOL)
            for bid, outcome in resolved.items():
                statuses[bid] = outcome
                if outcome[0] == "CONTAINER_INSTALL":
                    missing.discard(bid)
            if diagnostics:
                log = POOL / "container_diagnostics" / f"{container}.log"
                log.parent.mkdir(parents=True, exist_ok=True)
                log.write_text(diagnostics + "\n", encoding="utf-8")
        print(f"after container fallback: {len(wanted) - len(missing)}/{len(wanted)} resolved", flush=True)

    # ------------------------------------------------------------ symbolize
    totals: dict[str, int] = defaultdict(int)
    for target in targets:
        out_root = RESULTS_ROOT / target / "Dataset_symbolized"
        rows = []
        for tgt, rel, bid, stripped, truncated in inventory:
            if tgt != target:
                continue
            if truncated:
                status, detail = "TRUNCATED", "dataset copy truncated and no intact copy found"
            elif not stripped:
                status, detail = "HAS_SYMTAB", ""
            elif not bid:
                status, detail = "NO_BUILD_ID", ""
            elif statuses.get(bid, ("",))[0] not in RESOLVED:
                status, detail = statuses.get(bid, ("NOT_FOUND", ""))
            else:
                debug = POOL / "build-id" / f"{bid}.debug"
                work = out_root / rel
                source = work.with_name(work.name + ".stripped")
                work.rename(source)
                error = symbolize(source, debug, work)
                status, detail = ("UNSTRIP_FAILED", error) if error else ("SYMBOLIZED", str(debug))
                if error:
                    source.rename(work)
                else:
                    source.unlink()
            totals[status] += 1
            origin = REPLACED.get((target, str(rel))) or ADDED.get((target, str(rel))) or ""
            rows.append((str(rel), bid, status, detail, origin))
        write_tsv(out_root / "symbols.tsv", ("path", "gnu_build_id", "status", "detail", "source_override"), rows)
        counts = defaultdict(int)
        for row in rows:
            counts[row[2]] += 1
        print(f"[{target}] " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())), flush=True)

    print("Total: " + ", ".join(f"{k}={v}" for k, v in sorted(totals.items())), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
