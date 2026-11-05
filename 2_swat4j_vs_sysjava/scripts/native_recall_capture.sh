#!/usr/bin/env bash
#
# Runtime ground truth for the bytecode stage: which native methods does the
# JVM actually link while a JDK 8 target starts up?
#
# Each target is started in a fresh container (bench-jni-<target>, so the
# pipeline's et_<target> containers are untouched) with JAVA_TOOL_OPTIONS=
# -verbose:jni. HotSpot then logs every native method it binds, both lazily
# resolved symbols ("[Dynamic-linking native method C.m ... JNI]") and
# RegisterNatives tables ("[Registering JNI native method C.m]"). The run
# lasts until the target's readiness marker appears, plus SETTLE seconds.
#
# Usage: scripts/native_recall_capture.sh <target> [...]
#   targets as in run_jdk8_target.sh, e.g. solr_8.7.0-jdk8-buster
# Output: Final_results_JDK8/_native_recall/<target>/{jni.log,runtime_natives.txt}
#
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_ROOT="${REPO}/Final_results_JDK8/_native_recall"
MAX_WAIT="${MAX_WAIT:-180}"
SETTLE="${SETTLE:-30}"

for T in "$@"; do
    # Same image, arguments and readiness marker as run_jdk8_target.sh.
    case "$T" in
        elasticsearch_7.5.2-jdk8-buster)
            IMAGE=elasticsearch:7.5.2-jdk8-buster; # ES ignores JAVA_TOOL_OPTIONS, so the flag goes into ES_JAVA_OPTS.
            RUN_ARGS=(-e "ES_JAVA_OPTS=-Xms1g -Xmx1g -verbose:jni"); CMD=(); MARKER=" started" ;;
        groovy_4.0.0-jdk8-buster)
            IMAGE=groovy:4.0.0-jdk8-buster; RUN_ARGS=(); CMD=(); MARKER="Groovy 4.0.0 on" ;;
        solr_8.7.0-jdk8-buster)
            IMAGE=solr:8.7.0-jdk8-buster; RUN_ARGS=(); CMD=(); MARKER="Started @" ;;
        storm_2.4.0-jdk8-buster)
            IMAGE=storm:2.4.0-jdk8-buster; RUN_ARGS=(--network et-jdk8-net)
            CMD=(nimbus); MARKER="" ;;
        jetty_9.4.51-jdk8-buster)
            IMAGE=jetty:9.4.51-jdk8-buster; RUN_ARGS=(); CMD=(); MARKER="Started @" ;;
        *) echo "unknown target $T" >&2; exit 1 ;;
    esac
    out="${OUT_ROOT}/${T}"
    name="bench-jni-${T//[^A-Za-z0-9_.-]/-}"
    mkdir -p "$out"
    docker rm -f "$name" >/dev/null 2>&1 || true
    if [ "$T" = storm_2.4.0-jdk8-buster ]; then
        # Nimbus halts without ZooKeeper; reuse the pipeline's instance.
        docker inspect et-jdk8-zookeeper >/dev/null 2>&1 || { echo "et-jdk8-zookeeper not running" >&2; exit 1; }
    fi
    docker run -d --name "$name" -e JAVA_TOOL_OPTIONS=-verbose:jni "${RUN_ARGS[@]}" "$IMAGE" "${CMD[@]}" >/dev/null
    waited=0
    while [ $waited -lt "$MAX_WAIT" ]; do
        if [ -n "$MARKER" ] && docker logs "$name" 2>&1 | grep -qF "$MARKER"; then
            break
        fi
        sleep 5; waited=$((waited + 5))
    done
    ready=$([ -n "$MARKER" ] && docker logs "$name" 2>&1 | grep -qF "$MARKER" && echo yes || echo no)
    sleep "$SETTLE"
    docker logs "$name" > "${out}/jni.log" 2>&1 || true
    docker rm -f "$name" >/dev/null 2>&1 || true
    { grep -oE '\[(Dynamic-linking native method|Registering JNI native method) [^ ]+' "${out}/jni.log" || true; } \
        | awk '{sub(/\]$/, "", $NF); print $NF}' | sort -u > "${out}/runtime_natives.txt"
    printf '%s\tready=%s\twaited=%ss\truntime_natives=%s\n' "$T" "$ready" "$waited" "$(wc -l < "${out}/runtime_natives.txt")"
done
