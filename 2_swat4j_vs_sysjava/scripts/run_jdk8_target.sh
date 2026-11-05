#!/usr/bin/env bash
#
# End-to-end EchoTrace run for one of the Debian 10 + JDK 8 rebuilt targets,
# with debug symbols restored before SysPart.
#
#   dynamic capture -> extraction -> bytecode -> native mapping
#   -> debug symbols (symbolize_dataset.py) -> SysPart (libs, binaries,
#   unanalysed loaded libs, JNA/FFI) -> seccomp profile -> runtime check
#
# Usage: scripts/run_jdk8_target.sh <target> [first-stage]
#   target: elasticsearch_7.5.2-jdk8-buster | groovy_4.0.0-jdk8-buster |
#           solr_8.7.0-jdk8-buster | storm_2.4.0-jdk8-buster |
#           jetty_9.4.51-jdk8-buster
#           official JDK 8 images: zookeeper_3.4.14 | tomcat_7.0 | cassandra_3.0.29 |
#           orientdb_3.2.19 | jruby_9.4.2.0
#           rebuilt on Debian 10: cassandra_3.0.29-jdk8-buster |
#           orientdb_3.2.19-jdk8-buster | jruby_9.4.2.0-jdk8-buster
#   first-stage: resume from this stage number (1-10), default 1
#
# Each target runs in its own workspace (jdk8_workspaces/<target>/) holding a
# private copy of scripts/: the pipeline writes several files at the
# repository root (jna_ffi_analysis/, dynamic_leftover_*, progress logs), so
# targets sharing one root would overwrite each other. The workspace's
# SysPartCode links to SysPartLowmem (same SysPart, low-memory JSON/syscall
# steps). The sysdig capture and the debug-symbol stage take a lock, since they
# share sysdig and the symbol pool. Results land in Final_results_JDK8/<target>/.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "${SCRIPT_DIR}/.." && pwd)"
T="${1:?target required}"
FIRST="${2:-1}"

# target -> image | extra docker run args | command | readiness log marker
case "$T" in
    elasticsearch_7.5.2-jdk8-buster)
        IMAGE=elasticsearch:7.5.2-jdk8-buster; RUN_ARGS=(-e "ES_JAVA_OPTS=-Xms1g -Xmx1g"); CMD=(); MARKER=" started" ;;
    groovy_4.0.0-jdk8-buster)
        IMAGE=groovy:4.0.0-jdk8-buster; RUN_ARGS=(); CMD=(); MARKER="Groovy 4.0.0 on" ;;
    solr_8.7.0-jdk8-buster)
        IMAGE=solr:8.7.0-jdk8-buster; RUN_ARGS=(); CMD=(); MARKER="Started @" ;;
    storm_2.4.0-jdk8-buster)
        # Nimbus halts without ZooKeeper (3.5+): et-jdk8-zookeeper on et-jdk8-net.
        IMAGE=storm:2.4.0-jdk8-buster; RUN_ARGS=(--network et-jdk8-net --hostname nimbus --network-alias nimbus)
        CMD=(nimbus); MARKER="" ;;
    jetty_9.4.51-jdk8-buster)
        IMAGE=jetty:9.4.51-jdk8-buster; RUN_ARGS=(); CMD=(); MARKER="Started @" ;;
    zookeeper_3.4.14)
        IMAGE=zookeeper:3.4.14; RUN_ARGS=(); CMD=(); MARKER="binding to port" ;;
    tomcat_7.0)
        IMAGE=tomcat:7.0; RUN_ARGS=(); CMD=(); MARKER="Server startup in" ;;
    cassandra_3.0.29)
        IMAGE=cassandra:3.0.29; RUN_ARGS=(-e MAX_HEAP_SIZE=1G -e HEAP_NEWSIZE=256M); CMD=()
        MARKER="Starting listening for CQL clients" ;;
    orientdb_3.2.19)
        IMAGE=orientdb:3.2.19; RUN_ARGS=(-e ORIENTDB_ROOT_PASSWORD=root); CMD=(); MARKER="OrientDB Studio available" ;;
    jruby_9.4.2.0)
        # irb needs a terminal and prints nothing: ready = JVM up for 30 s.
        IMAGE=jruby:9.4.2.0; RUN_ARGS=(-it); CMD=(); MARKER="" ;;
    # cassandra/orientdb/jruby rebuilt on debian:buster-slim + Temurin 8u504
    # (DockerFiles/jdk8-buster/); same run arguments and ready lines.
    cassandra_3.0.29-jdk8-buster)
        IMAGE=cassandra:3.0.29-jdk8-buster; RUN_ARGS=(-e MAX_HEAP_SIZE=1G -e HEAP_NEWSIZE=256M); CMD=()
        MARKER="Starting listening for CQL clients" ;;
    orientdb_3.2.19-jdk8-buster)
        IMAGE=orientdb:3.2.19-jdk8-buster; RUN_ARGS=(-e ORIENTDB_ROOT_PASSWORD=root); CMD=(); MARKER="OrientDB Studio available" ;;
    jruby_9.4.2.0-jdk8-buster)
        # irb needs a terminal and prints nothing: ready = JVM up for 30 s.
        IMAGE=jruby:9.4.2.0-jdk8-buster; RUN_ARGS=(-it); CMD=(); MARKER="" ;;
    zookeeper_3.4.14)
        IMAGE=zookeeper:3.4.14; RUN_ARGS=(); CMD=(); MARKER="binding to port" ;;
    tomcat_7.0)
        IMAGE=tomcat:7.0; RUN_ARGS=(); CMD=(); MARKER="Server startup in" ;;
    cassandra_3.0.29)
        IMAGE=cassandra:3.0.29; RUN_ARGS=(-e MAX_HEAP_SIZE=1G -e HEAP_NEWSIZE=256M); CMD=()
        MARKER="Starting listening for CQL clients" ;;
    orientdb_3.2.19)
        IMAGE=orientdb:3.2.19; RUN_ARGS=(-e ORIENTDB_ROOT_PASSWORD=root); CMD=(); MARKER="OrientDB Studio available" ;;
    jruby_9.4.2.0)
        # irb needs a terminal and prints nothing: ready = JVM up for 30 s.
        IMAGE=jruby:9.4.2.0; RUN_ARGS=(-it); CMD=(); MARKER="" ;;
    *) echo "unknown target $T" >&2; exit 1 ;;
esac

CNAME="et_${T}"
WS="${REPO}/jdk8_workspaces/${T}"
FINAL="${REPO}/Final_results_JDK8/${T}"
LOCKS="${REPO}/jdk8_workspaces/.locks"
mkdir -p "$WS" "$FINAL" "$LOCKS"
LOG="${FINAL}/pipeline_run.log"
exec > >(tee -a "$LOG") 2>&1

stage() { echo; echo "===== [$(date '+%F %T')] ${T} stage $1: $2"; }
# SKIP_STAGES="6": leave those stages' results as they are (e.g. keep the
# symbolized dataset when only the bytecode analysis changed).
run_from() { [ "$FIRST" -le "$1" ] && [[ " ${SKIP_STAGES:-} " != *" $1 "* ]]; }

ready() {  # wait until the app is up: log marker, or (storm) nimbus.log line
    local deadline=$((SECONDS + ${1:-180}))
    while [ $SECONDS -lt $deadline ]; do
        [ "$(docker inspect -f '{{.State.Running}}' "$CNAME" 2>/dev/null)" = true ] || return 1
        if [ -n "$MARKER" ]; then
            docker logs "$CNAME" 2>&1 | grep -q -- "$MARKER" && return 0
        elif [ "${T#storm}" = "$T" ]; then
            started="$(docker inspect -f '{{.State.StartedAt}}' "$CNAME")"
            [ $(( $(date +%s) - $(date -d "$started" +%s) )) -ge 30 ] \
                && docker top "$CNAME" -eo pid,args | grep -q java && return 0
        else
            docker exec "$CNAME" grep -q "Starting nimbus server" /opt/storm/logs/nimbus.log 2>/dev/null && return 0
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
    ln -sfn "${REPO}/SysPartLowmem" "${WS}/SysPartCode"
    cp "${REPO}/runc.txt" "${WS}/runc.txt"
    if [ "$T" = storm_2.4.0-jdk8-buster ]; then
        docker network inspect et-jdk8-net >/dev/null 2>&1 || docker network create et-jdk8-net >/dev/null
        docker inspect et-jdk8-zookeeper >/dev/null 2>&1 \
            || docker run -d --name et-jdk8-zookeeper --network et-jdk8-net --network-alias zookeeper zookeeper:3.7 >/dev/null
    fi
    docker container rm -f "$CNAME" >/dev/null 2>&1 || true
    docker run -d --name "$CNAME" "${RUN_ARGS[@]}" "$IMAGE" "${CMD[@]}" >/dev/null
    ready 240 && echo "container up: $CNAME" || { echo "container did not become ready"; exit 1; }
fi

export IMG_NAME="$T"
export JARFILES_DIR="${WS}/JARFILES_${T}" LIBS_DIR="${WS}/LIBS_${T}" BINARIES_DIR="${WS}/BINARIES_${T}"
export RUNTIME_DIR="${WS}/RUNTIME_${T}" OUTPUTS_DIR="${WS}/outputs_${T}"
export JARFILES_IMAGE="$JARFILES_DIR" LIBS_IMAGE="$LIBS_DIR"

# ----------------------------------------------------------- dynamic capture
if run_from 2; then
    stage 2 "sysdig capture (120 s, clean start)"
    # sysdig_unified.sh kills its `timeout` wrapper after the window but leaves
    # the sudo/sysdig children running; a leftover would hold the capture lock
    # and disturb the next capture. So: no sysdig may be running when a capture
    # starts, and this capture's own sysdig is stopped when it ends. flock -o
    # keeps the lock out of the children, so a leftover cannot hold it.
    capture() {
        sudo pkill -f "sysdig --modern-bpf container.name=et_" 2>/dev/null || true
        bash "${WS}/scripts/sysdig_unified.sh" "$CNAME" 120
        local rc=$?
        sudo pkill -f "sysdig --modern-bpf container.name=${CNAME} " 2>/dev/null || true
        return $rc
    }
    export -f capture; export WS CNAME
    flock -o "${LOCKS}/sysdig" bash -c capture
    ready 240 && echo "container running again after capture" || { echo "container not ready after capture"; exit 1; }
fi

if run_from 3; then
    stage 3 "extract JDK runtime, JARs, native libraries"
    bash "${WS}/scripts/extract_runtime_and_jar_libs.sh" "$CNAME"
fi

# --------------------------------------------------------- bytecode analysis
# Rerunnable: stage 9's organize step moves workspace outputs (bytecode
# outputs included) into Final_results/<target>/; bring them back first.
if [ "$FIRST" -ge 4 ] && [ -d "${WS}/Final_results/${T}" ]; then
    for part in Dataset Bytecode_Analysis Dynamic_Analysis Binary_Analysis Reports; do
        for e in "${WS}/Final_results/${T}/${part}"/*; do
            [ -e "$e" ] && [ ! -e "${WS}/$(basename "$e")" ] && mv "$e" "${WS}/"
        done
    done
fi
if run_from 4; then
    stage 4 "bytecode analysis (JNADetector)"
    mkdir -p "$OUTPUTS_DIR"
    java -Xmx16g -cp "${REPO}/target/classes:$(cat "${REPO}/jdk8_workspaces/.classpath")" \
        com.echotrace.app.bytecode_new.JNADetector "$JARFILES_DIR" "$OUTPUTS_DIR" "$RUNTIME_DIR"
fi

if run_from 5; then
    stage 5 "native mapping and start functions"
    bash "${WS}/scripts/prepare_native_mapping.sh"
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
    RESULTS_ROOT="${REPO}/Final_results_JDK8" flock "${LOCKS}/symbols" \
        python3 "${REPO}/scripts/symbolize_dataset.py" "$T"
    # The SysPart drivers search LIBS_ and its JDK*_LIBS subfolders only, so the
    # dependencies copied from the container go next to the other libraries.
    if [ -d "${SYM}/LIBS_${T}/_container_deps" ]; then
        cp -n "${SYM}/LIBS_${T}/_container_deps/"* "${SYM}/LIBS_${T}/" 2>/dev/null || true
    fi
    bash "${REPO}/scripts/relink_sonames.sh" "${SYM}/LIBS_${T}" >/dev/null
fi
SLIBS="${SYM}/LIBS_${T}"
SBINS="${SYM}/BINARIES_${T}"

# ------------------------------------------------------------------- SysPart
cd "$WS"
if run_from 7; then
    stage 7 "SysPart: mapped libraries and executed binaries"
    # Drop SysPart results from an earlier run so this one starts clean.
    rm -rf "${WS}/syscalls_output_${T}" "${WS}/syscalls_BIN_${T}" "${WS}/syscalls_unanalysed_${T}" \
        "${WS}/startfuncs_unanalysed_${T}" "${WS}/jna_ffi_analysis" "${WS}"/dynamic_leftover_after_analyzed_ldd.* \
        "${WS}/unanalysed_syspart_progress.log"
    bash "${WS}/scripts/automate_syscall_analysis.sh" \
        --binary-dir "$SLIBS" --binaries-dir "$SBINS" --startfunc-dir "$OUTPUTS_DIR" \
        --output-dir "${WS}/syscalls_output_${T}" --img-name "$T" --log
fi

if run_from 8; then
    stage 8 "SysPart: unanalysed loaded libraries and JNA/FFI bindings"
    python3 "${WS}/scripts/report_dynamic_leftover_after_analyzed_ldd.py" \
        --libs-dir "$SLIBS" --syscalls-dir "${WS}/syscalls_output_${T}"
    python3 "${WS}/scripts/analyze_unanalysed_loaded_libs.py" --libs-dir "$SLIBS" --run-syspart
    python3 "${WS}/scripts/analyse_jna_ffi.py" --libs-dir "$SLIBS" --outputs-dir "$OUTPUTS_DIR" --run-syspart
fi

# --------------------------------------------------------- seccomp profile
PROFILE_NAME="${T}.json"
if run_from 9; then
    stage 9 "merge syscalls into seccomp profile, assemble results"
    python3 "${WS}/scripts/merge_all_syscalls.py" "$T"
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
if run_from 10; then
    stage 10 "run the container under its profile"
    VERIFY_MARKER="$MARKER" bash "${REPO}/scripts/verify_seccomp_profile.sh" "$T" "$IMAGE" "$PROFILE" \
        "${FINAL}/Binary_Analysis/syscalls_output_${T}/seccomp_runtime_test.log" -- "${RUN_ARGS[@]}" -- "${CMD[@]}"
fi

stage done "finished; profile: ${PROFILE}"
