#!/usr/bin/env bash
#
# Check that a container still works under its generated seccomp profile.
#
# Usage:
#   VERIFY_MARKER='<log line>' scripts/verify_seccomp_profile.sh <target> <image> <profile.json> <log> \
#       -- <docker run args...> -- <command...>
#
# Runs the same workload twice -- once without a profile (baseline) and once
# with --security-opt seccomp=<profile> -- and records, for the profiled run:
#   ready      the app reached its readiness marker (log line, or for storm
#              "Starting nimbus server" in nimbus.log)
#   running    still running STAY seconds after becoming ready
#   probe      it answers from the host: HTTP for elasticsearch/solr/jetty
#   eperm      "Operation not permitted" lines beyond the baseline's count;
#              the profiles default to SCMP_ACT_ERRNO, so a missing syscall
#              shows up as EPERM rather than a crash
# Probes run from the host or with docker cp, never docker exec: an exec'd tool
# would itself run under the profile and fail for reasons unrelated to the app.
#
# RESULT=PASS when all four hold, otherwise FAIL with the reasons.
#
set -uo pipefail

T="$1"; IMAGE="$2"; PROFILE="$3"; LOG="$4"; shift 4
[ "${1:-}" = "--" ] && shift
RUN_ARGS=()
while [ $# -gt 0 ] && [ "$1" != "--" ]; do RUN_ARGS+=("$1"); shift; done
[ "${1:-}" = "--" ] && shift
CMD=("$@")
MARKER="${VERIFY_MARKER:-}"
STAY="${STAY:-60}"
READY_TIMEOUT="${READY_TIMEOUT:-240}"
SAFE="$(echo "$T" | tr '._' '--')"

log_has_marker() {  # container
    if [ -n "$MARKER" ]; then
        docker logs "$1" 2>&1 | grep -q -- "$MARKER"
    elif [ "${T#storm}" = "$T" ]; then  # no ready line: JVM up for 30 s
        local started; started="$(docker inspect -f '{{.State.StartedAt}}' "$1")"
        [ $(( $(date +%s) - $(date -d "$started" +%s) )) -ge 30 ] && docker top "$1" -eo pid,args | grep -q java
    else
        local tmp; tmp="$(mktemp)"
        docker cp "$1:/opt/storm/logs/nimbus.log" "$tmp" >/dev/null 2>&1 \
            && grep -q "Starting nimbus server" "$tmp" && ! grep -q "Halting process" "$tmp"
        local rc=$?; rm -f "$tmp"; return $rc
    fi
}

wait_ready() {  # container -> seconds to ready, or nonzero
    local start=$SECONDS
    while [ $((SECONDS - start)) -lt "$READY_TIMEOUT" ]; do
        [ "$(docker inspect -f '{{.State.Running}}' "$1" 2>/dev/null)" = true ] || return 1
        log_has_marker "$1" && { echo $((SECONDS - start)); return 0; }
        sleep 2
    done
    return 1
}

probe() {  # container -> "ok <detail>" or "fail <detail>"
    local ip port path
    ip="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' "$1" | awk '{print $1}')"
    case "$T" in
        elasticsearch*) port=9200; path=/ ;;
        solr*) port=8983; path="/solr/admin/info/system?wt=json" ;;
        jetty*) port=8080; path=/ ;;
        *) log_has_marker "$1" && echo "ok marker-still-present" || echo "fail marker-lost"; return ;;
    esac
    local code
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "http://${ip}:${port}${path}")"
    # Any HTTP answer means the server accepted, read and wrote on a socket;
    # jetty's empty base answers 404, which still counts.
    [ "${code:-000}" != 000 ] && echo "ok http_${code} ${path}" || echo "fail no_http_answer ${path}"
}

eperm_count() { docker logs "$1" 2>&1 | grep -ciE "operation not permitted|EPERM" || true; }

run_case() {  # name, extra-args...
    local name="$1"; shift
    docker container rm -f "$name" >/dev/null 2>&1 || true
    docker run -d --name "$name" "$@" "${RUN_ARGS[@]}" "$IMAGE" "${CMD[@]}" 2>&1
}

{
    echo "container=${T}"
    echo "image=${IMAGE}"
    echo "profile=${PROFILE}"
    echo "profile_syscalls=$(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(sum(len(s['names']) for s in d['syscalls']), d['defaultAction'])" "$PROFILE")"
    echo "workload=docker run ${RUN_ARGS[*]} ${IMAGE} ${CMD[*]}"
    echo "started_at=$(date -Iseconds)"
    echo

    BASE="echotrace-verify-base-${SAFE}"; SEC="echotrace-verify-seccomp-${SAFE}"
    echo "---- baseline (no profile) ----"
    echo "docker_run_output=$(run_case "$BASE")"
    base_ready="$(wait_ready "$BASE")" && echo "baseline_ready_after=${base_ready}s" || echo "baseline_ready=NO"
    sleep "$STAY"
    base_state="$(docker inspect -f '{{.State.Status}} exit={{.State.ExitCode}}' "$BASE")"
    base_probe="$(probe "$BASE")"
    base_eperm="$(eperm_count "$BASE")"
    echo "baseline_state=${base_state}"; echo "baseline_probe=${base_probe}"; echo "baseline_eperm_lines=${base_eperm}"
    docker container rm -f "$BASE" >/dev/null 2>&1

    echo
    echo "---- with seccomp profile ----"
    echo "docker run -d --name ${SEC} --security-opt seccomp=${PROFILE} ${RUN_ARGS[*]} ${IMAGE} ${CMD[*]}"
    echo "docker_run_output=$(run_case "$SEC" --security-opt "seccomp=${PROFILE}")"
    reasons=()
    if sec_ready="$(wait_ready "$SEC")"; then echo "ready_after=${sec_ready}s"; else echo "ready=NO"; reasons+=(not_ready); fi
    sleep "$STAY"
    sec_state="$(docker inspect -f '{{.State.Status}} exit={{.State.ExitCode}}' "$SEC")"
    echo "state_after_${STAY}s=${sec_state}"
    case "$sec_state" in running*) ;; *) reasons+=(not_running) ;; esac
    sec_probe="$(probe "$SEC")"; echo "probe=${sec_probe}"
    case "$sec_probe" in ok*) ;; *) reasons+=(probe_failed) ;; esac
    sec_eperm="$(eperm_count "$SEC")"; echo "eperm_lines=${sec_eperm} (baseline ${base_eperm})"
    [ "${sec_eperm:-0}" -gt "${base_eperm:-0}" ] && reasons+=(new_eperm_errors)

    echo
    if [ ${#reasons[@]} -eq 0 ]; then echo "RESULT=PASS"; else echo "RESULT=FAIL ${reasons[*]}"; fi
    echo "finished_at=$(date -Iseconds)"
    echo
    echo "---- docker logs tail (with profile) ----"
    docker logs "$SEC" 2>&1 | tail -25
    if [ "${sec_eperm:-0}" -gt 0 ]; then
        echo; echo "---- EPERM lines (with profile) ----"
        docker logs "$SEC" 2>&1 | grep -iE "operation not permitted|EPERM" | head -20
    fi
    docker container rm -f "$SEC" >/dev/null 2>&1
} > "$LOG" 2>&1

grep -E "^RESULT=" "$LOG"
