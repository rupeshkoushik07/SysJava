#!/usr/bin/env bash
#
# One-time setup for reproducing the SysJava results.
#
#   SYSPART_ROOT=/path/to/SysPartCode ./setup.sh
#
# 1. checks the required tools
# 2. builds the EchoTrace (SysJava) bytecode analysis in echotrace/ (Maven)
# 3. fetches the OpenJDK 8 native sources SWAT4J's mapper reads (swat4j/.tmp_jdk8_native)
# 4. creates one working copy per pipeline:
#      work/latest/  (Table tab:latest,  pipelines/latest/scripts)
#      work/jdk8/    (Table tab:results, pipelines/jdk8/scripts)
#    each = echotrace/ + the pipeline's scripts + runc.txt + a SysPart link tree.
#
# SYSPART_ROOT must point at a built SysPartCode checkout (see syspart/README.md):
#   $SYSPART_ROOT/analysis/app/build_x86_64/syspart must exist.
#
set -euo pipefail
ART="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYSPART_ROOT="${SYSPART_ROOT:-}"

need() { command -v "$1" >/dev/null 2>&1 || { echo "missing: $1 ($2)"; MISSING=1; }; }
MISSING=0
need docker   "container runs, Docker 24+"
need sysdig   "dynamic capture; must run with sudo and --modern-bpf"
need java     "JDK 17+ for the bytecode analysis"
need mvn      "Maven 3.8+ to build echotrace/"
need python3  "Python 3.10+"
need nm       "binutils"
need objdump  "binutils"
need readelf  "binutils"
need eu-unstrip "elfutils: attach debug symbols"
need dpkg-deb "unpack Debian -dbgsym/-dbg packages for debug symbols"
need git      "fetch OpenJDK 8 sources"
need objcopy  "binutils"
need debuginfod-find "elfutils: debug symbols by Build ID"
need curl     "download -dbgsym/-dbg packages"
[ "$MISSING" = 0 ] || { echo "install the tools above and rerun"; exit 1; }
java -version 2>&1 | head -1

if [ -z "$SYSPART_ROOT" ] || [ ! -x "$SYSPART_ROOT/analysis/app/build_x86_64/syspart" ]; then
    echo "SYSPART_ROOT must point at a built SysPartCode checkout (see syspart/README.md)"; exit 1
fi
echo "SysPart: $SYSPART_ROOT (syspart md5 $(md5sum "$SYSPART_ROOT/analysis/app/build_x86_64/syspart" | cut -c1-12); pinned 3618898bddb1)"

# ------------------------------------------------------------ build echotrace
echo "== building echotrace/"
(cd "$ART/echotrace" && mvn -q -DskipTests compile \
    && mvn -q dependency:build-classpath -Dmdep.outputFile=target/.classpath)

# --------------------------------------------- OpenJDK 8 sources for SWAT4J
JDK8U_COMMIT=24fbffc3f77f72e322a962c2c9eb7ba538eb52e1   # the checkout the SWAT4J mapper used
if [ ! -d "$ART/swat4j/.tmp_jdk8_native/jdk/src/share/native" ]; then
    echo "== fetching OpenJDK 8u native sources (jdk8u @ ${JDK8U_COMMIT:0:7}) for the SWAT4J mapper"
    D="$ART/swat4j/.tmp_jdk8_native"
    git init -q "$D" && git -C "$D" remote add origin https://github.com/openjdk/jdk8u.git
    git -C "$D" sparse-checkout set jdk/src/share/native
    git -C "$D" fetch -q --depth 1 origin "$JDK8U_COMMIT" && git -C "$D" checkout -q FETCH_HEAD
fi

# ------------------------------------------------------------ working copies
syspart_tree() {  # <dest> <work repo>: symlink tree into SYSPART_ROOT, low-memory syscall step
    local dest="$1" repo="$2"
    rm -rf "$dest"; mkdir -p "$dest"
    cp -rs "$SYSPART_ROOT/analysis" "$dest/analysis"
    rm -f "$dest/analysis/app/src/scripts/compute_syscalls.sh"
    ln -s "$repo/scripts/compute_syscalls_lowmem.sh" "$dest/analysis/app/src/scripts/compute_syscalls.sh"
}

for p in latest jdk8; do
    W="$ART/work/$p"
    echo "== work/$p"
    mkdir -p "$W"
    rsync -a --delete --exclude target/ "$ART/echotrace/" "$W/"
    rsync -a "$ART/echotrace/target/" "$W/target/"
    rsync -a --delete "$ART/pipelines/$p/scripts/" "$W/scripts/"
    cp "$ART/pipelines/$p/runc.txt" "$W/runc.txt"
    mkdir -p "$W/artifacts/all-running-containers/debug-symbols"
    syspart_tree "$W/SysPartCode" "$W"
done
# JDK 8 pipeline: runtime set includes the runc 1.3.4 init syscalls, the
# workspaces read the classpath from jdk8_workspaces/, SysPart via SysPartLowmem,
# and the five images are rebuilt locally from DockerFiles/jdk8-buster.
cat "$ART/pipelines/jdk8/runc_host_1.3.4_additions.txt" >> "$ART/work/jdk8/runc.txt"
mkdir -p "$ART/work/jdk8/jdk8_workspaces"
cp "$ART/work/jdk8/target/.classpath" "$ART/work/jdk8/jdk8_workspaces/.classpath"
syspart_tree "$ART/work/jdk8/SysPartLowmem" "$ART/work/jdk8"
rsync -a "$ART/pipelines/jdk8/DockerFiles/" "$ART/work/jdk8/DockerFiles/"

echo
echo "Setup done. Next:"
echo "  1_latest_containers/reproduce.sh      # Table tab:latest"
echo "  2_swat4j_vs_sysjava/reproduce.sh      # Table tab:results (5 JDK 8 rebuilds)"
