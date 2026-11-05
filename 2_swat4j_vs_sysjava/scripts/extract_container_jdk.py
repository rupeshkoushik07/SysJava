#!/usr/bin/env python3
"""
extract_container_jdk.py - extract JDK runtime artifacts from a Docker container.

By default, copies JDK runtime JARs into RUNTIME_<IMG_NAME>/.
With --libs or --libs-only, also (or only) copies *.so files into
LIBS_<IMG_NAME>/JDK<N>_LIBS/.

Usage:
    python3 scripts/extract_container_jdk.py <container_name> [options]

    # JARs only (default, backward compatible)
    python3 scripts/extract_container_jdk.py my-container

    # JARs + .so files
    python3 scripts/extract_container_jdk.py my-container --libs

    # .so files only (no JARs)
    python3 scripts/extract_container_jdk.py my-container --libs-only

Options:
    --force                Re-extract even if output dirs already exist.
    --out-name=<name>      Override IMG_NAME in output paths.
    --runtime-dir=<path>   Output directory for JDK jars (overrides RUNTIME_IMG_NAME env).
    --libs                 Also extract .so files into LIBS_<IMG_NAME>/JDK<N>_LIBS/.
    --libs-only            Only extract .so files (skip JAR extraction).
    --libs-dir=<path>      Override .so output parent dir (default: LIBS_<IMG_NAME>/).
    --project-root=<path>  Base directory for LIBS output (default: cwd).

IMG_NAME is derived from the container image name (not the container name/ID):

    cassandra:5.0.6-bookworm  -> cassandra_5.0.6-bookworm
    solr:8.7.0-slim           -> solr_8.7.0-slim
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

# JDK 8 layout: which .jar files in $JAVA_HOME/lib to copy.  rt.jar is the
# bulk of the runtime; the others contribute charsets, security, JSSE, etc.
JDK8_RUNTIME_JARS = ["rt.jar", "charsets.jar", "resources.jar", "jsse.jar", "jce.jar"]


def run(cmd, capture=True, check=True):
    """Run a command, return stdout as text."""
    proc = subprocess.run(cmd, capture_output=capture, text=True, check=check)
    return proc.stdout.strip() if capture else ""


def docker_exec(container: str, sh_command: str) -> str:
    return run(["docker", "exec", container, "sh", "-c", sh_command])


def detect_java_home(container: str) -> str:
    # Try JAVA_HOME env, then resolve 'java' on PATH, then probe common bundled locations.
    out = docker_exec(container, """
        if [ -n "$JAVA_HOME" ]; then echo "$JAVA_HOME"; exit 0; fi
        JP=$(command -v java 2>/dev/null) && JP=$(readlink -f "$JP") && echo "${JP%/bin/java}" && exit 0
        for d in /usr/share/*/jdk /usr/local/openjdk-* /usr/lib/jvm/java-*; do
            [ -x "$d/bin/java" ] && echo "$d" && exit 0
        done
        exit 1
    """.strip())
    if not out:
        raise RuntimeError(f"Could not determine JAVA_HOME inside {container}")
    return out.splitlines()[-1]


def detect_jdk_major(container: str, java_home: str) -> int:
    """Return major version (8, 9, 11, 17, 21, 25, ...)."""
    out = docker_exec(container,
                      f'{java_home}/bin/java -XshowSettings:properties -version 2>&1 '
                      '| awk -F"=" "/java.specification.version/{gsub(/ /,\\"\\",\\$2); print \\$2}"')
    spec = out.strip()
    if spec == "1.8":
        return 8
    m = re.match(r"^(\d+)$", spec)
    if not m:
        raise RuntimeError(f"Unrecognised java.specification.version={spec!r} in {container}")
    return int(m.group(1))


def container_has_jmods(container: str, java_home: str) -> bool:
    rc = subprocess.run(["docker", "exec", container, "sh", "-c",
                         f"test -d {java_home}/jmods"],
                        capture_output=True).returncode
    return rc == 0


def img_name_from_image(image: str) -> str:
    """Convert a Docker image reference like 'cassandra:5.0.6-bookworm' or
    'docker.elastic.co/elasticsearch/elasticsearch:7.17.18' into a
    filesystem-safe identifier matching the project's JARFILES_* convention:

        cassandra:5.0.6-bookworm                              -> cassandra_5.0.6-bookworm
        zookeeper:3.4.14                                      -> zookeeper_3.4.14
        solr:8.7.0-slim                                       -> solr_8.7.0-slim
        docker.elastic.co/elasticsearch/elasticsearch:7.17.18 -> docker.elastic.co_elasticsearch_elasticsearch_7.17.18

    Hyphens are preserved (they're typically image-tag flavour suffixes like
    -slim, -bookworm).  Other separators (':', '/', whitespace) become '_'.
    """
    return re.sub(r"[^A-Za-z0-9._-]", "_", image)


def resolve_image_name(container: str) -> str:
    """Look up the image name for a running container.  Accepts both names
    and IDs; returns the original container reference if inspection fails so
    the caller can fall back gracefully."""
    try:
        out = run(["docker", "inspect", "--format", "{{.Config.Image}}", container])
        if out:
            return out
    except subprocess.CalledProcessError:
        pass
    return container


# ============================================================
# JAR extraction (JDK runtime classes)
# ============================================================

def extract_jdk8(container: str, java_home: str, out_dir: Path) -> None:
    """Copy rt.jar and friends from $JAVA_HOME/lib/ on the container."""
    out_dir.mkdir(parents=True, exist_ok=True)
    # Some JDK 8 images use $JAVA_HOME/lib/, others use $JAVA_HOME/jre/lib/.
    candidate_dirs = [f"{java_home}/lib", f"{java_home}/jre/lib"]
    for jar_name in JDK8_RUNTIME_JARS:
        copied = False
        for d in candidate_dirs:
            try:
                run(["docker", "exec", container, "test", "-f", f"{d}/{jar_name}"], check=True)
            except subprocess.CalledProcessError:
                continue
            run(["docker", "cp", f"{container}:{d}/{jar_name}", str(out_dir / jar_name)])
            print(f"  copied: {jar_name} (from {d})")
            copied = True
            break
        if not copied:
            print(f"  skip:   {jar_name} (not present in container)")
    # ext jars: best-effort
    try:
        ext_listing = docker_exec(container, f"ls {java_home}/lib/ext/*.jar 2>/dev/null").splitlines()
    except subprocess.CalledProcessError:
        ext_listing = []
    if ext_listing:
        ext_out = out_dir / "ext"
        ext_out.mkdir(exist_ok=True)
        for path in ext_listing:
            name = os.path.basename(path)
            run(["docker", "cp", f"{container}:{path}", str(ext_out / name)])
        print(f"  copied: {len(ext_listing)} ext jars to ext/")


def extract_jmods(container: str, java_home: str, out_dir: Path) -> None:
    """Copy each $JAVA_HOME/jmods/*.jmod, repack as a flat JAR (strip classes/)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    listing = docker_exec(container, f"ls {java_home}/jmods/*.jmod").splitlines()
    if not listing:
        raise RuntimeError(f"No jmods found in {java_home}/jmods/")
    for jmod_path in listing:
        jmod_name = Path(jmod_path).stem  # strips .jmod
        with tempfile.NamedTemporaryFile(suffix=".jmod", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            run(["docker", "cp", f"{container}:{jmod_path}", str(tmp_path)])
            target_jar = out_dir / f"{jmod_name}.jar"
            _repack_jmod_to_jar(tmp_path, target_jar)
            with zipfile.ZipFile(target_jar) as z:
                count = len(z.namelist())
            print(f"  repacked: {jmod_name}.jar ({count} entries)")
        finally:
            tmp_path.unlink(missing_ok=True)


def _repack_jmod_to_jar(jmod_path: Path, jar_path: Path) -> None:
    """Read a .jmod (which has a 4-byte JMOD magic prefix) using ZipFile (which
    locates the central directory at the end and tolerates the prefix), strip
    the 'classes/' prefix, drop everything else (cmds, conf, lib, native)."""
    with zipfile.ZipFile(jmod_path, "r") as src, \
            zipfile.ZipFile(jar_path, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            if info.is_dir():
                continue
            if not info.filename.startswith("classes/"):
                continue
            stripped = info.filename[len("classes/"):]
            if not stripped.endswith(".class"):
                continue
            with src.open(info) as fin:
                dst.writestr(stripped, fin.read(), compress_type=zipfile.ZIP_DEFLATED)


def extract_jrt(container: str, java_home: str, out_dir: Path, major: int) -> None:
    """Extract JRT modules from a JRE-only image, preferring host jimage."""
    out_dir.mkdir(parents=True, exist_ok=True)
    completion_marker = out_dir / ".jrt-extraction-complete"
    host_jimage = _find_host_jimage(major)
    if host_jimage is not None:
        _extract_jrt_with_host_jimage(container, java_home, out_dir, host_jimage)
        completion_marker.write_text("JRT module extraction completed\n", encoding="utf-8")
        return

    dumper_jar = _ensure_jrt_dumper_jar()
    cont_tmp = "/tmp/_extract_container_jdk"
    container_jar = f"{cont_tmp}/JrtDumper.jar"
    container_out = f"{cont_tmp}/jars"

    # Recover completed module JARs from a previous attempt. Validate them on
    # the host: a SIGKILL from the old all-at-once dumper could leave a
    # non-empty but truncated JAR in the container work directory.
    docker_exec(container, f"mkdir -p {cont_tmp} {container_out}")
    run(["docker", "cp", str(dumper_jar), f"{container}:{container_jar}"])
    try:
        run(["docker", "cp", f"{container}:{container_out}/.", str(out_dir)])
    except subprocess.CalledProcessError:
        pass
    for candidate in out_dir.glob("*.jar"):
        try:
            with zipfile.ZipFile(candidate) as archive:
                if not archive.infolist():
                    raise zipfile.BadZipFile("CRC check failed")
        except (OSError, zipfile.BadZipFile):
            candidate.unlink(missing_ok=True)
    docker_exec(container, f"rm -f {container_out}/*.jar {container_out}/*.tmp")
    # Seed the container-side work directory from any host-side partial result
    # (for example, if the previous container was replaced after interruption).
    for completed_jar in out_dir.glob("*.jar"):
        run(["docker", "cp", str(completed_jar),
             f"{container}:{container_out}/{completed_jar.name}"])
    java = shlex.quote(f"{java_home}/bin/java")
    jar = shlex.quote(container_jar)
    target_dir = shlex.quote(container_out)
    # SerialGC and a modest heap keep total JVM memory below the default
    # container limit while still allowing JrtDumper to stream class files.
    command = (
        "set -eu; "
        f"{java} --list-modules | cut -d@ -f1 | while IFS= read -r module; do "
        f"[ -n \"$module\" ] || continue; "
        f"if [ -s {target_dir}/\"$module\".jar ]; then "
        "echo \"Skipping completed module $module\"; continue; fi; "
        "echo \"Dumping module $module\"; "
        f"if {java} -Xms16m -Xmx128m -XX:+UseSerialGC -cp {jar} "
        f"JrtDumper {target_dir} \"$module\"; then :; else "
        f"rc=$?; rm -f {target_dir}/\"$module\".jar; exit $rc; fi; "
        "done"
    )
    print(f"  dumping JRT modules individually inside {container} (heap capped at 128 MiB)...")
    try:
        out = docker_exec(container, command)
    except subprocess.CalledProcessError as exc:
        completion_marker.unlink(missing_ok=True)
        try:
            run(["docker", "cp", f"{container}:{container_out}/.", str(out_dir)])
        except subprocess.CalledProcessError:
            pass
        detail = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(
            f"JRT module extraction failed (docker exec exit {exc.returncode}). "
            "Completed module JARs were kept; rerun the extractor to resume."
            + (f"\n{detail}" if detail else "")
        ) from exc
    print("  " + out.replace("\n", "\n  "))
    run(["docker", "cp", f"{container}:{container_out}/.", str(out_dir)])
    completion_marker.write_text("JRT module extraction completed\n", encoding="utf-8")
    docker_exec(container, f"rm -rf {cont_tmp}")


def _find_host_jimage(major: int) -> Path | None:
    """Find a local jimage utility from the same JDK major version."""
    candidates = []
    path_tool = shutil.which("jimage")
    if path_tool:
        candidates.append(Path(path_tool))
    candidates.extend(sorted(Path("/usr/lib/jvm").glob("*/bin/jimage")))
    seen = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            version = run([str(candidate), "--version"])
        except (OSError, subprocess.CalledProcessError):
            continue
        match = re.search(r"\b(\d+)(?:\.\d+)*\b", version)
        if match and int(match.group(1)) == major:
            return candidate
    return None


def _extract_jrt_with_host_jimage(container: str, java_home: str,
                                  out_dir: Path, jimage: Path) -> None:
    """Copy the compact JRE module image and unpack it with local jimage.

    This avoids launching a memory-hungry Java process in a constrained
    application container. The host tool must match the JDK major version.
    """
    modules_path = f"{java_home}/lib/modules"
    for stale in out_dir.glob("*.jar.tmp"):
        stale.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="echotrace-jrt-") as work:
        work_dir = Path(work)
        image_file = work_dir / "modules"
        extracted_dir = work_dir / "extracted"
        extracted_dir.mkdir()
        print(f"  copying JRT image from container ({modules_path})...")
        run(["docker", "cp", f"{container}:{modules_path}", str(image_file)])
        print(f"  extracting JRT image with host tool {jimage}...")
        run([str(jimage), "extract", f"--dir={extracted_dir}", str(image_file)])

        modules = sorted(path for path in extracted_dir.iterdir() if path.is_dir())
        if not modules:
            raise RuntimeError(f"jimage extracted no modules from {modules_path}")

        for module_dir in modules:
            target = out_dir / f"{module_dir.name}.jar"
            temporary_target = out_dir / f"{module_dir.name}.jar.tmp"
            temporary_target.unlink(missing_ok=True)
            with zipfile.ZipFile(temporary_target, "w", compression=zipfile.ZIP_DEFLATED) as jar:
                for path in sorted(module_dir.rglob("*")):
                    if path.is_file():
                        jar.write(path, path.relative_to(module_dir).as_posix())
            os.replace(temporary_target, target)
            print(f"  packed: {target.name}")


def _ensure_jrt_dumper_jar() -> Path:
    """Build scripts/lib/JrtDumper.jar from JrtDumper.java if missing/stale."""
    here = Path(__file__).resolve().parent
    src = here / "lib" / "JrtDumper.java"
    jar = here / "lib" / "JrtDumper.jar"
    if jar.exists() and jar.stat().st_mtime >= src.stat().st_mtime:
        return jar
    if not src.exists():
        raise RuntimeError(f"Missing source: {src}")
    print(f"  building JrtDumper.jar from {src}...")
    with tempfile.TemporaryDirectory() as build:
        run(["javac", "--release", "9", "-d", build, str(src)])
        run(["jar", "cf", str(jar), "-C", build, "JrtDumper.class"])
    return jar


# ============================================================
# .so extraction (JDK native libraries)
# ============================================================

def resolve_jdk_lib_path(container: str, java_home: str) -> str:
    """Return container path to JDK lib dir. Prefer jre/lib/ (JDK 8), else lib/ (JDK 9+)."""
    for rel in ("jre/lib", "lib"):
        path = f"{java_home}/{rel}"
        rc = subprocess.run(
            ["docker", "exec", container, "test", "-d", path],
            capture_output=True,
        ).returncode
        if rc == 0:
            return path
    raise RuntimeError(
        f"No lib/ or jre/lib under JAVA_HOME={java_home!r} in container {container}"
    )


def list_so_files_in_container(container: str, lib_src: str) -> list:
    """Return .so file paths relative to lib_src (e.g. server/libjvm.so)."""
    qdir = shlex.quote(lib_src)
    cmd = f"cd {qdir} && find . -type f -name '*.so'"
    proc = subprocess.run(
        ["docker", "exec", container, "sh", "-c", cmd],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"find failed in container (exit {proc.returncode}): {proc.stderr.strip()}"
        )
    rels = []
    for line in proc.stdout.splitlines():
        line = line.strip().replace("\\", "/")
        if not line:
            continue
        if line.startswith("./"):
            line = line[2:]
        if line.endswith(".so"):
            rels.append(line)
    return sorted(set(rels))


def extract_jdk_libs(container: str, java_home: str, major: int,
                     dest: Path, force: bool) -> int:
    """Copy .so files from container's JDK lib dir to dest/JDK<N>_LIBS/.
    Returns number of .so files copied, or -1 on error."""
    lib_src = resolve_jdk_lib_path(container, java_home)
    jdk_libs_dir = dest / f"JDK{major}_LIBS"

    print(f"\n--- .so extraction ---")
    print(f"  copy from    = {lib_src}/")
    print(f"  copy to      = {jdk_libs_dir}/")

    if jdk_libs_dir.exists():
        if force:
            shutil.rmtree(jdk_libs_dir)
        else:
            print(f"  reusing existing {jdk_libs_dir}/  (use --force to re-extract)")
            return 0

    jdk_libs_dir.mkdir(parents=True)

    try:
        rels = list_so_files_in_container(container, lib_src)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return -1

    if not rels:
        print(f"WARN: No .so files under {lib_src} in container.", file=sys.stderr)
        return 0

    for rel in rels:
        cont_path = f"{lib_src.rstrip('/')}/{rel}"
        local_path = jdk_libs_dir / rel
        local_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["docker", "cp", f"{container}:{cont_path}", str(local_path)],
            check=True,
        )

    print(f"  Copied {len(rels)} .so file(s) into {jdk_libs_dir}/")
    return len(rels)


# ============================================================
# Main
# ============================================================

def main() -> int:
    ap = argparse.ArgumentParser(
            formatter_class=argparse.RawDescriptionHelpFormatter,
            description=__doc__)
    ap.add_argument("container", help="Docker container name (must be running)")
    ap.add_argument("--force", action="store_true",
                    help="Re-extract even if output dirs already exist")
    ap.add_argument("--out-name", default=None,
                    help="Override IMG_NAME used in output paths")
    ap.add_argument("--runtime-dir", default=None,
                    help="JDK jar output directory (overrides RUNTIME_IMG_NAME env)")
    libs_group = ap.add_mutually_exclusive_group()
    libs_group.add_argument("--libs", action="store_true",
                            help="Also extract .so files into LIBS_<IMG_NAME>/JDK<N>_LIBS/")
    libs_group.add_argument("--libs-only", action="store_true",
                            help="Only extract .so files (skip JAR extraction)")
    ap.add_argument("--libs-dir", default=None,
                    help="Override .so output parent dir (default: LIBS_<IMG_NAME>/)")
    ap.add_argument("--project-root", type=Path, default=Path.cwd(),
                    help="Base directory for LIBS output (default: cwd)")
    args = ap.parse_args()

    container = args.container
    if args.out_name:
        safe = args.out_name
        image_ref = None
    else:
        image_ref = resolve_image_name(container)
        safe = img_name_from_image(image_ref)

    env_runtime = os.environ.get("RUNTIME_IMG_NAME", "").strip()
    if args.runtime_dir:
        jdk_dir = Path(args.runtime_dir)
    elif env_runtime:
        jdk_dir = Path(env_runtime)
    else:
        jdk_dir = Path(f"RUNTIME_{safe}")

    print(f"=== Container: {container} ===")
    if image_ref and image_ref != container:
        print(f"  image     = {image_ref}")
    print(f"  IMG_NAME  = {safe}")
    java_home = detect_java_home(container)
    major = detect_jdk_major(container, java_home)
    has_jmods = container_has_jmods(container, java_home) if major >= 9 else False
    print(f"  JAVA_HOME = {java_home}")
    print(f"  JDK major = {major}")
    print(f"  jmods/    = {'present' if has_jmods else 'absent (JRE image)' if major >= 9 else 'n/a (JDK 8)'}")

    # --- JAR extraction ---
    do_jars = not args.libs_only
    if do_jars:
        if jdk_dir.exists() and not args.force:
            if major >= 9 and not has_jmods and not (jdk_dir / ".jrt-extraction-complete").is_file():
                print(f"  resuming incomplete JRT extraction in {jdk_dir}/...")
                extract_jrt(container, java_home, jdk_dir, major)
            else:
                print(f"  reusing existing {jdk_dir}/  (use --force to re-extract)")
        else:
            if jdk_dir.exists():
                shutil.rmtree(jdk_dir)
            if major == 8:
                extract_jdk8(container, java_home, jdk_dir)
            elif has_jmods:
                extract_jmods(container, java_home, jdk_dir)
            else:
                extract_jrt(container, java_home, jdk_dir, major)
        print()
        print(f"JDK runtime jars: {jdk_dir.resolve()}/")

    # --- .so extraction ---
    do_libs = args.libs or args.libs_only
    if do_libs:
        if args.libs_dir:
            libs_parent = Path(args.libs_dir)
        else:
            libs_parent = (args.project_root / f"LIBS_{safe}").resolve()
        rc = extract_jdk_libs(container, java_home, major, libs_parent, args.force)
        if rc < 0:
            return 1
        print(f"JDK native libs:  {libs_parent.resolve()}/JDK{major}_LIBS/")

    return 0


if __name__ == "__main__":
    sys.exit(main())
