#!/usr/bin/env bash
#
# Static reproduction: rebuild one image's seccomp allowlist from the shipped
# call graphs. No SysPart, no sysdig, no root, no debug symbols.
#
#   ./whitelist.sh <image>            e.g. ./whitelist.sh zookeeper_3.9.5
#   ./whitelist.sh all                every image with shipped results
#
# Steps (pipeline stage numbers of run_latest_target.sh in brackets):
#   1. start the pinned image                                         [1]
#   2. copy out the JARs, libraries and executables the shipped sysdig
#      capture lists, and the container's JDK                         [2, 3]
#   3. bytecode analysis: native methods and their bindings           [4]
#   4. native mapping: start functions per library                    [5]
#   5. parse the shipped SysPart call graphs from those start
#      functions to the reachable syscalls (tools/replay_syspart.py)  [6-8]
#   6. merge with the runtime set into the seccomp profile            [10]
#   7. compare with the shipped profile
#
# Output: <table folder>/whitelists_static/<image>.json, plus
#   <image>.report.tsv   one line per call graph (ok / not mapped / new library)
#   <image>.diff.txt     syscalls added or missing against the shipped profile
# Work files: work/static/<image>/
#
# Needs Docker, JDK 17+, Maven, Python 3, binutils. RESULTS=<dir> reads shipped
# results from another folder (default: the table folder's results).
# KEEP_CONTAINER=1 leaves the container running. ECHOTRACE=<dir> runs the
# bytecode analysis from another build of the tool (default: echotrace/).
set -euo pipefail
ART="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
T="${1:?usage: ./whitelist.sh <image>|all}"
ET="${ECHOTRACE:-$ART/echotrace}"

if [ "$T" = all ]; then
    rc=0
    for d in "$ART"/1_latest_containers/results/*/ "$ART"/2_swat4j_vs_sysjava/sysjava_results/*/; do
        [ -d "$d/Binary_Analysis" ] || continue
        "$0" "$(basename "$d")" || { echo "!! $(basename "$d") failed"; rc=1; }
    done
    exit $rc
fi

# ------------------------------------------------------------ which table
if [ -d "$ART/1_latest_containers/results/$T" ] || grep -q "^    $T)" "$ART/1_latest_containers/scripts/run_latest_target.sh"; then
    TABLE="$ART/1_latest_containers"; DRIVER="$TABLE/scripts/run_latest_target.sh"
    SHIPPED="${RESULTS:-$TABLE/results}/$T"; ZK_IMAGE=zookeeper:3.9.5; ZK_NAME=et-latest-zookeeper
else
    TABLE="$ART/2_swat4j_vs_sysjava"; DRIVER="$TABLE/scripts/run_jdk8_target.sh"
    SHIPPED="${RESULTS:-$TABLE/sysjava_results}/$T"; ZK_IMAGE=zookeeper:3.7; ZK_NAME=et-jdk8-zookeeper
fi
grep -q "^    $T)" "$DRIVER" || { echo "unknown image $T"; exit 1; }
[ -d "$SHIPPED/Binary_Analysis" ] || { echo "no shipped results for $T in $SHIPPED"; exit 1; }

# Image, docker run arguments, readiness marker and the readiness check come
# from the pipeline driver itself, so both modes start the container the same way.
LOGFILE=""
eval "$(sed -n '/^case "\$T" in/,/^esac/p' "$DRIVER")"
eval "$(sed -n '/^ready() {/,/^}/p' "$DRIVER")"
CNAME="et_static_${T}"

WS="$ART/work/static/$T"
OUT="$TABLE/whitelists_static"
rm -rf "$WS"; mkdir -p "$WS" "$OUT"
LOG="$WS/whitelist.log"
exec > >(tee "$LOG") 2>&1
step() { echo; echo "===== [$(date '+%F %T')] $T: $*"; }

cp -a "$TABLE/scripts" "$WS/scripts"
if [ -f "$SHIPPED/runtime_set.txt" ]; then
    cp "$SHIPPED/runtime_set.txt" "$WS/runc.txt"
else
    cp "$TABLE/runc.txt" "$WS/runc.txt"
    [ "$TABLE" = "$ART/2_swat4j_vs_sysjava" ] && cat "$TABLE/runc_host_1.3.4_additions.txt" >> "$WS/runc.txt"
fi

# ------------------------------------------------------------ bytecode tool
if [ ! -f "$ET/target/.classpath" ]; then
    step "building $ET (once)"
    (cd "$ET" && mvn -q -DskipTests compile \
        && mvn -q dependency:build-classpath -Dmdep.outputFile=target/.classpath)
fi

# ------------------------------------------------------------ 1. container
step "1. start $IMAGE"
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    ref="$(awk -F'\t' -v t="$IMAGE" '$1==t{print $2}' "$ART/docker_images/images.tsv")"
    case "$ref" in
        *@sha256:*) docker pull "$ref" && docker tag "$ref" "$IMAGE" ;;
        build*|"") bash "$ART/docker_images/build_jdk8_images.sh" "${T%%_*}" ;;
        *) docker pull "$ref" ;;
    esac
fi
for a in "${RUN_ARGS[@]}"; do
    if [ "${prev:-}" = --network ]; then
        docker network inspect "$a" >/dev/null 2>&1 || docker network create "$a" >/dev/null
        [ "$(docker inspect -f '{{.State.Running}}' "$ZK_NAME" 2>/dev/null)" = true ] || {
            docker rm -f "$ZK_NAME" >/dev/null 2>&1 || true
            docker run -d --name "$ZK_NAME" --network "$a" --network-alias zookeeper "$ZK_IMAGE" >/dev/null; }
    fi
    prev="$a"
done
docker rm -f "$CNAME" >/dev/null 2>&1 || true
docker run -d --name "$CNAME" "${RUN_ARGS[@]}" "$IMAGE" "${CMD[@]}" >/dev/null
trap '[ -n "${KEEP_CONTAINER:-}" ] || docker rm -f "$CNAME" >/dev/null 2>&1 || true' EXIT
ready 300 && echo "container up: $CNAME" || { echo "container did not become ready"; exit 1; }

export IMG_NAME="$T"
export JARFILES_DIR="$WS/JARFILES_$T" LIBS_DIR="$WS/LIBS_$T" BINARIES_DIR="$WS/BINARIES_$T"
export RUNTIME_DIR="$WS/RUNTIME_$T" OUTPUTS_DIR="$WS/outputs_$T"
export JARFILES_IMAGE="$JARFILES_DIR" LIBS_IMAGE="$LIBS_DIR"

# ------------------------------------------------------- 2. copy inputs
step "2. copy the files listed in the shipped capture, and the container's JDK"
cp -a "$SHIPPED/Dynamic_Analysis/sysdig_outputs_$T" "$WS/sysdig_outputs_$T"
# The extraction part of sysdig_unified.sh (its header and STEP 6), without the capture.
awk '/^# --- STEP 1:/{skip=1} /^# --- STEP 6:/{skip=0} !skip' \
    "$WS/scripts/sysdig_unified.sh" > "$WS/scripts/copy_captured_files.sh"
bash "$WS/scripts/copy_captured_files.sh" "$CNAME" | tail -12
bash "$WS/scripts/extract_runtime_and_jar_libs.sh" "$CNAME" | tail -5
# Libraries the copied ELFs need but the capture did not list (e.g. libutil for a
# JNA binding): copied from the container as the debug-symbol stage [6] does,
# with the same function, and placed next to the other libraries.
mkdir -p "$WS/_deps_root" && mv "$LIBS_DIR" "$BINARIES_DIR" "$WS/_deps_root/"
(cd "$WS/scripts" && python3 -c 'import sys; from pathlib import Path; import symbolize_dataset as s
added = s.complete_dependencies(sys.argv[1], Path(sys.argv[2]))
print("container dependencies added: %d %s" % (len(added), " ".join(added)))' "static_$T" "$WS/_deps_root")
mv "$WS/_deps_root/LIBS_$T" "$WS/_deps_root/BINARIES_$T" "$WS/" && rmdir "$WS/_deps_root"
if [ -d "$LIBS_DIR/_container_deps" ]; then cp -n "$LIBS_DIR/_container_deps/"* "$LIBS_DIR/" 2>/dev/null || true; fi
bash "$WS/scripts/relink_sonames.sh" "$LIBS_DIR" >/dev/null
echo "copied: $(find "$JARFILES_DIR" -name '*.jar' | wc -l) JARs, $(find "$LIBS_DIR" -name '*.so*' | wc -l) libraries," \
     "$(find "$BINARIES_DIR" -type f 2>/dev/null | wc -l) executables"

# ------------------------------------------------- 3. bytecode analysis
step "3. bytecode analysis (JNADetector)"
mkdir -p "$OUTPUTS_DIR"
java -Xmx16g -cp "$ET/target/classes:$(cat "$ET/target/.classpath")" \
    com.echotrace.app.bytecode_new.JNADetector "$JARFILES_DIR" "$OUTPUTS_DIR" "$RUNTIME_DIR" \
    > "$WS/bytecode.log" 2>&1 || { tail -20 "$WS/bytecode.log"; exit 1; }
echo "native methods: $(wc -l < "$OUTPUTS_DIR/native_methods.txt")" \
     "(shipped: $(wc -l < "$SHIPPED/Bytecode_Analysis/outputs_$T/native_methods.txt" 2>/dev/null || echo ?))"

# ---------------------------------------------------- 4. native mapping
step "4. native mapping and start functions"
(cd "$WS" && bash scripts/prepare_native_mapping.sh > "$WS/mapping.log" 2>&1) || { tail -20 "$WS/mapping.log"; exit 1; }
(cd "$WS" && python3 scripts/analyse_jna_ffi.py --libs-dir "$LIBS_DIR" --outputs-dir "$OUTPUTS_DIR" \
    > "$WS/jna_ffi.log" 2>&1) || true
echo "libraries with start functions: $(find "$OUTPUTS_DIR" -name '*.so*.txt' | wc -l)"

# ------------------------------------------- 5. parse the call graphs
step "5. syscalls from the shipped call graphs"
python3 "$ART/tools/whitelist_from_callgraphs.py" "$T" "$SHIPPED/Binary_Analysis" "$WS"
cp "$WS/static_report.tsv" "$OUT/$T.report.tsv"

# ------------------------------------------------------------- 6. merge
step "6. seccomp profile"
(cd "$WS" && python3 scripts/merge_all_syscalls.py "$T" > "$WS/merge.log" 2>&1) || true
[ -s "$WS/syscalls_output_$T/$T.json" ] || { tail -30 "$WS/merge.log"; echo "no profile written"; exit 1; }
cp "$WS/syscalls_output_$T/$T.json" "$OUT/$T.json"

# ----------------------------------------------------------- 7. compare
step "7. compare with the shipped profile"
names() { python3 -c 'import json,sys; [print(n) for g in json.load(open(sys.argv[1]))["syscalls"] for n in g["names"]]' "$1" | sort -u; }
REF="$SHIPPED/Binary_Analysis/syscalls_output_$T/$T.json"
{
    echo "rerun:   $(names "$OUT/$T.json" | wc -l) syscalls  ($OUT/$T.json)"
    echo "shipped: $(names "$REF" | wc -l) syscalls  ($REF)"
    echo "only in rerun:   $(comm -23 <(names "$OUT/$T.json") <(names "$REF") | tr '\n' ' ')"
    echo "only in shipped: $(comm -13 <(names "$OUT/$T.json") <(names "$REF") | tr '\n' ' ')"
} | tee "$OUT/$T.diff.txt"
if cmp -s <(names "$OUT/$T.json") <(names "$REF"); then echo "RESULT: identical to the shipped profile"
else echo "RESULT: differs from the shipped profile (see $OUT/$T.report.tsv)"; fi
