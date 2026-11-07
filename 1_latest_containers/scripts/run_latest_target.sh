#!/usr/bin/env bash
#
# End-to-end EchoTrace run for one of the newer-version images (paper Table
# "latest": JDK 8-25 on Debian 12 / Ubuntu 22.04-26.04 / CentOS 7), from the
# merged code at 516fb46 (JNI mapping keeps every overload target) with debug
# symbols restored before SysPart:
#
#   dynamic capture -> extraction -> bytecode -> native mapping (+ overload
#   check) -> debug symbols -> SysPart (libs, binaries, unanalysed loaded libs,
#   JNA/FFI) -> seccomp profile -> run the container under the profile
#
# Usage: scripts/run_latest_target.sh <target> [first-stage]
#   target: cassandra_5.0.8 | zookeeper_3.9.5 | tomcat_11.0.22 | solr_10.0.0 |
#           groovy_5.0.6 | orientdb_3.2.53 | jetty_12.1.10 |
#           elasticsearch_7.1.0 | storm_2.8.8 | jruby_10.1.0.0
#   first-stage: resume from this stage number (1-11), default 1
#
# Target names, container names (et_<target>) and folders all carry the
# version, so they never collide with the older-version runs. Each target runs
# in its own workspace (workspaces/<target>/) with a private copy of scripts/,
# because the pipeline writes files at the repository root. SysPartCode here is
# a link tree to the pinned 2026-06-24 SysPart build (see SysPartCode/README.md).
# The sysdig capture and the debug-symbol stage take locks: they share sysdig
# and the symbol pool. Results land in Final_results_latest_versions/<target>/.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "${SCRIPT_DIR}/.." && pwd)"
T="${1:?target required}"
FIRST="${2:-1}"

# target -> image | docker run args | command | readiness marker | marker file
# The image tag must equal the target's version: sysdig_unified.sh names its
# output folders after the image tag. tomcat:11.0.22, orientdb:3.2.53 and
# storm:2.8.8 are local tags of tomcat:11.0, orientdb:latest and storm:latest.
LOGFILE=""
case "$T" in
    cassandra_5.0.8)
        IMAGE=cassandra:5.0.8; RUN_ARGS=(-e MAX_HEAP_SIZE=1G -e HEAP_NEWSIZE=256M); CMD=(); MARKER="Startup complete" ;;
    zookeeper_3.9.5)
        IMAGE=zookeeper:3.9.5; RUN_ARGS=(); CMD=(); MARKER="binding to port" ;;
    tomcat_11.0.22)
        IMAGE=tomcat:11.0.22; RUN_ARGS=(); CMD=(); MARKER="Server startup in" ;;
    solr_10.0.0)
        IMAGE=solr:10.0.0; RUN_ARGS=(); CMD=(); MARKER="o.e.j.s.Server Started" ;;
    groovy_5.0.6)
        # groovysh needs a terminal to stay up.
        IMAGE=groovy:5.0.6; RUN_ARGS=(-it); CMD=(); MARKER="Groovy Shell" ;;
    orientdb_3.2.53)
        IMAGE=orientdb:3.2.53; RUN_ARGS=(-e ORIENTDB_ROOT_PASSWORD=root); CMD=(); MARKER="Listening http connections" ;;
    jetty_12.1.10)
        IMAGE=jetty:12.1.10; RUN_ARGS=(); CMD=(); MARKER="oejs.Server:main: Started" ;;
    elasticsearch_7.1.0)
        IMAGE=elasticsearch:7.1.0
        RUN_ARGS=(-e discovery.type=single-node -e "ES_JAVA_OPTS=-Xms1g -Xmx1g"); CMD=(); MARKER='"message": "started"' ;;
    storm_2.8.8)
        # Nimbus halts without ZooKeeper: et-latest-zookeeper on et-latest-net.
        IMAGE=storm:2.8.8; RUN_ARGS=(--network et-latest-net --hostname nimbus --network-alias nimbus)
        CMD=(storm nimbus); MARKER="Starting nimbus server"; LOGFILE=/logs/nimbus.log ;;
    jruby_10.1.0.0)
        # irb needs a terminal and prints nothing: ready = JVM up after 30 s.
        IMAGE=jruby:10.1.0.0; RUN_ARGS=(-it); CMD=(); MARKER="" ;;
    *) echo "unknown target $T" >&2; exit 1 ;;
esac

CNAME="et_${T}"
# WS_ROOT / RESULTS_ROOT / LAST_STAGE let a partial rerun (e.g. the clinit-fix rerun into
# Final_results_latest_versions_clinit) use its own folders and stop after a given stage.
WS="${WS_ROOT:-${REPO}/workspaces}/${T}"
RESULTS_ROOT="${RESULTS_ROOT:-${REPO}/Final_results_latest_versions}"
FINAL="${RESULTS_ROOT}/${T}"
LOCKS="${REPO}/workspaces/.locks"
mkdir -p "$WS" "$FINAL" "$LOCKS"
LOG="${FINAL}/pipeline_run.log"
exec > >(tee -a "$LOG") 2>&1

stage() { echo; echo "===== [$(date '+%F %T')] ${T} stage $1: $2"; }
run_from() { [ "$FIRST" -le "$1" ] && [ "$1" -le "${LAST_STAGE:-11}" ]; }

ready() {  # wait until the app is up (same rule as verify_seccomp_profile.sh)
    local deadline=$((SECONDS + ${1:-240})) started
    while [ $SECONDS -lt $deadline ]; do
        [ "$(docker inspect -f '{{.State.Running}}' "$CNAME" 2>/dev/null)" = true ] || return 1
        if [ -n "$LOGFILE" ]; then
            docker exec "$CNAME" grep -q -- "$MARKER" "$LOGFILE" 2>/dev/null && return 0
        elif [ -n "$MARKER" ]; then
            docker logs "$CNAME" 2>&1 | grep -q -- "$MARKER" && return 0
        else
            started="$(docker inspect -f '{{.State.StartedAt}}' "$CNAME")"
            [ $(( $(date +%s) - $(date -d "$started" +%s) )) -ge 30 ] \
                && docker top "$CNAME" -eo pid,args | grep -q java && return 0
        fi
        sleep 3
    done
    return 1
}

# ---------------------------------------------------------------- workspace
if run_from 1; then
    stage 1 "workspace and container"
    rm -rf "${WS}/scripts"
    cp -a "${REPO}/scripts" "${WS}/scripts"
    ln -sfn "${REPO}/SysPartCode" "${WS}/SysPartCode"
    cp "${REPO}/runc.txt" "${WS}/runc.txt"
    if [ "$T" = storm_2.8.8 ]; then
        docker network inspect et-latest-net >/dev/null 2>&1 || docker network create et-latest-net >/dev/null
        [ "$(docker inspect -f '{{.State.Running}}' et-latest-zookeeper 2>/dev/null)" = true ] || {
            docker rm -f et-latest-zookeeper >/dev/null 2>&1 || true
            docker run -d --name et-latest-zookeeper --network et-latest-net --network-alias zookeeper zookeeper:3.9.5 >/dev/null; }
    fi
    docker container rm -f "$CNAME" >/dev/null 2>&1 || true
    docker run -d --name "$CNAME" "${RUN_ARGS[@]}" "$IMAGE" "${CMD[@]}" >/dev/null
    ready 300 && echo "container up: $CNAME ($IMAGE)" || { echo "container did not become ready"; exit 1; }
fi

export IMG_NAME="$T"
export JARFILES_DIR="${WS}/JARFILES_${T}" LIBS_DIR="${WS}/LIBS_${T}" BINARIES_DIR="${WS}/BINARIES_${T}"
export RUNTIME_DIR="${WS}/RUNTIME_${T}" OUTPUTS_DIR="${WS}/outputs_${T}"
export JARFILES_IMAGE="$JARFILES_DIR" LIBS_IMAGE="$LIBS_DIR"

# ----------------------------------------------------------- dynamic capture
if run_from 2; then
    stage 2 "sysdig capture (120 s, clean start)"
    flock "${LOCKS}/sysdig" bash "${WS}/scripts/sysdig_unified.sh" "$CNAME" 120
    ready 300 && echo "container running again after capture" || { echo "container not ready after capture"; exit 1; }
fi

if run_from 3; then
    stage 3 "extract JDK runtime, JARs, native libraries"
    bash "${WS}/scripts/extract_runtime_and_jar_libs.sh" "$CNAME"
    # A capture that saw no JARs or no native libraries missed the startup
    # (sysdig attached too late); capture once more with a longer init wait.
    nj=$(find "$JARFILES_DIR" -name '*.jar' 2>/dev/null | wc -l)
    nl=$(find "$LIBS_DIR" -name '*.so*' 2>/dev/null | wc -l)
    # Every target is a JVM: no libjvm.so means the startup burst was dropped.
    jvm=$(find "$LIBS_DIR" -name 'libjvm.so' 2>/dev/null | wc -l)
    echo "captured: ${nj} JARs, ${nl} native libraries, libjvm.so: ${jvm}"
    if [ "$nj" -eq 0 ] || [ "$nl" -eq 0 ] || [ "$jvm" -eq 0 ]; then
        echo "capture incomplete; retrying with SYSDIG_INIT_WAIT=60"
        rm -rf "${WS}/sysdig_outputs_${T}" "$JARFILES_DIR" "$LIBS_DIR" "$BINARIES_DIR"
        SYSDIG_INIT_WAIT=60 flock "${LOCKS}/sysdig" bash "${WS}/scripts/sysdig_unified.sh" "$CNAME" 120
        ready 300 || { echo "container not ready after capture retry"; exit 1; }
        bash "${WS}/scripts/extract_runtime_and_jar_libs.sh" "$CNAME"
        nj=$(find "$JARFILES_DIR" -name '*.jar' 2>/dev/null | wc -l)
        nl=$(find "$LIBS_DIR" -name '*.so*' 2>/dev/null | wc -l)
        echo "captured after retry: ${nj} JARs, ${nl} native libraries"
        jvm=$(find "$LIBS_DIR" -name 'libjvm.so' 2>/dev/null | wc -l)
        [ "$nj" -gt 0 ] && [ "$nl" -gt 0 ] && [ "$jvm" -gt 0 ] || { echo "capture still incomplete"; exit 1; }
    fi
fi

# --------------------------------------------------------- bytecode analysis
if run_from 4; then
    # DETECTOR_REPO selects the build that runs the bytecode detectors (default:
    # this worktree). The commit is recorded in FINAL/detector_commit.txt.
    DETECTOR_REPO="${DETECTOR_REPO:-$REPO}"
    DETECTOR_COMMIT="$(git -C "$DETECTOR_REPO" rev-parse --short HEAD)"
    stage 4 "bytecode analysis (JNADetector, code at ${DETECTOR_COMMIT} in ${DETECTOR_REPO})"
    mkdir -p "$OUTPUTS_DIR"
    printf 'stage4_detector_commit=%s\nstage4_detector_repo=%s\nstage4_detector_branch=%s\n' \
        "$DETECTOR_COMMIT" "$DETECTOR_REPO" "$(git -C "$DETECTOR_REPO" rev-parse --abbrev-ref HEAD)" \
        > "${FINAL}/detector_commit.txt"
    java -Xmx"${DETECTOR_HEAP:-16g}" -cp "${DETECTOR_REPO}/target/classes:$(cat "${DETECTOR_REPO}/target/.classpath")" \
        com.echotrace.app.bytecode_new.JNADetector "$JARFILES_DIR" "$OUTPUTS_DIR" "$RUNTIME_DIR"
fi

if run_from 5; then
    stage 5 "native mapping and start functions"
    bash "${WS}/scripts/prepare_native_mapping.sh"
    # Every overload of an overloaded JNI method must be mapped (PR #31).
    python3 "${WS}/scripts/check_jni_overloads.py" "$LIBS_DIR" "$OUTPUTS_DIR" "${FINAL}/jni_overload_check.tsv" \
        || echo "WARNING: overloaded JNI symbols missing from the mapping, see ${FINAL}/jni_overload_check.tsv"
fi

# -------------------------------------------------------------- debug symbols
SYM="${FINAL}/Dataset_symbolized"
if run_from 6; then
    stage 6 "debug symbols"
    mkdir -p "${FINAL}/Dataset"
    for d in JARFILES LIBS BINARIES RUNTIME; do
        rm -rf "${FINAL}/Dataset/${d}_${T}"
        cp -a "${WS}/${d}_${T}" "${FINAL}/Dataset/"
    done
    RESULTS_ROOT="$RESULTS_ROOT" flock "${LOCKS}/symbols" python3 "${REPO}/scripts/symbolize_dataset.py" "$T"
    # The SysPart drivers search LIBS_ and its subfolders by name, so the
    # dependencies copied from the container go next to the other libraries.
    if [ -d "${SYM}/LIBS_${T}/_container_deps" ]; then
        cp -n "${SYM}/LIBS_${T}/_container_deps/"* "${SYM}/LIBS_${T}/" 2>/dev/null || true
    fi
    bash "${REPO}/scripts/relink_sonames.sh" "${SYM}/LIBS_${T}" >/dev/null
    awk -F'\t' 'NR>1{c[$3]++} END{for(k in c) printf "%s=%d ", k, c[k]; print ""}' "${SYM}/symbols.tsv"
fi
SLIBS="${SYM}/LIBS_${T}"
SBINS="${SYM}/BINARIES_${T}"

# ------------------------------------------------------------------- SysPart
cd "$WS"
ulimit -s 1048576  # Egalito recursion depth on a full libjvm
if run_from 7; then
    stage 7 "SysPart: mapped libraries and executed binaries"
    bash "${WS}/scripts/automate_syscall_analysis.sh" \
        --binary-dir "$SLIBS" --binaries-dir "$SBINS" --startfunc-dir "$OUTPUTS_DIR" \
        --output-dir "${WS}/syscalls_output_${T}" --img-name "$T" --log \
        || echo "stage 7: automate_syscall_analysis exited $? (per-binary failures, e.g. symbol-less Go binaries like gosu, are listed above); continuing"
fi

if run_from 8; then
    stage 8 "SysPart: unanalysed loaded libraries and JNA/FFI bindings"
    python3 "${WS}/scripts/report_dynamic_leftover_after_analyzed_ldd.py" \
        --libs-dir "$SLIBS" --syscalls-dir "${WS}/syscalls_output_${T}"
    python3 "${WS}/scripts/analyze_unanalysed_loaded_libs.py" --libs-dir "$SLIBS" --run-syspart
    # Exits 1 when no bound library resolves in LIBS_ (e.g. jruby's jnr-ffi bindings to Windows
    # Kernel32 and Solaris libsocket): nothing to analyse, not a pipeline failure.
    python3 "${WS}/scripts/analyse_jna_ffi.py" --libs-dir "$SLIBS" --outputs-dir "$OUTPUTS_DIR" --run-syspart \
        || echo "stage 8: JNA/FFI analysis exited $? (bound libraries not in LIBS_, listed above); continuing"
fi

if run_from 9; then
    stage 9 "named call graphs: unnamed (fuzzyfunc) functions per result"
    for d in "${WS}/syscalls_output_${T}"/*/ "${WS}"/syscalls_BIN_"${T}"/*/; do
        [ -f "${d}allfunctions.txt" ] || continue
        printf '%s\tfunctions=%s\tfuzzy=%s\tsyscalls=%s\n' "$(basename "$d")" \
            "$(wc -l < "${d}allfunctions.txt")" "$(grep -c '^fuzzyfunc' "${d}allfunctions.txt" || true)" \
            "$(wc -l < "${d}syscalls.txt" 2>/dev/null || echo 0)"
    done | tee "${FINAL}/named_callgraph_summary.tsv"
fi

# --------------------------------------------------------- seccomp profile
PROFILE_NAME="${T}.json"
if run_from 10; then
    stage 10 "merge syscalls into seccomp profile, assemble results"
    # merge_all_syscalls.py exits 1 when any binary/library has no result (e.g. gosu)
    # even though it writes the profile; only a missing profile is fatal.
    python3 "${WS}/scripts/merge_all_syscalls.py" "$T" \
        || { [ -s "${WS}/syscalls_output_${T}/${T}.json" ] \
             && echo "stage 10: merge reported items without results (listed above); profile written, continuing" \
             || { echo "stage 10: merge wrote no profile"; exit 1; }; }
    ORGANIZE_TMP="${WS}/Final_results"
    rm -rf "$ORGANIZE_TMP"
    bash "${WS}/scripts/organize_results.sh" "$T"
    for part in Bytecode_Analysis Dynamic_Analysis Binary_Analysis; do
        rm -rf "${FINAL:?}/${part}"
        [ -d "${ORGANIZE_TMP}/${T}/${part}" ] && cp -a "${ORGANIZE_TMP}/${T}/${part}" "${FINAL}/"
    done
    for extra in "${ORGANIZE_TMP}/${T}"/*; do
        case "$(basename "$extra")" in Dataset|Bytecode_Analysis|Dynamic_Analysis|Binary_Analysis) ;; *) cp -a "$extra" "${FINAL}/" ;; esac
    done
fi
PROFILE="${FINAL}/Binary_Analysis/syscalls_output_${T}/${PROFILE_NAME}"

# ------------------------------------------------------------ verification
if run_from 11; then
    stage 11 "run the container under its profile"
    VERIFY_MARKER="$MARKER" VERIFY_LOGFILE="$LOGFILE" bash "${REPO}/scripts/verify_seccomp_profile.sh" \
        "$T" "$IMAGE" "$PROFILE" "${FINAL}/seccomp_runtime_test.log" -- "${RUN_ARGS[@]}" -- "${CMD[@]}"
fi

stage done "finished; profile: ${PROFILE}"
