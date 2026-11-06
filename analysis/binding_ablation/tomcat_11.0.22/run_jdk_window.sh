#!/bin/bash
# Tomcat 11 ablation, JDK libraries, under the limits agreed with the Manager
# session (host coordinator): one SysPart at a time, at niceness $NICE
# (default 10); each run starts only when available memory reaches its gate.
# While a run is active, available memory is watched:
#   GUARD=pause  SIGSTOP this run's syspart below 15 GB, SIGCONT above 30 GB
#   GUARD=kill   below $KILL_BELOW GB (default 20) kill the run and requeue it,
#                at most $MAX_REQUEUE times (default 2); after that, stop the
#                queue and say HOLD
# With RSS_STOP_GB set, a syspart whose resident memory passes it is stopped
# (SIGSTOP, once) and left for the Manager to decide; kill -CONT resumes it.
#
# Usage: run_jdk_window.sh [lib:arms ...]   e.g. libnet.so:B "libjava.so:A B"
# Without arguments: libnet B, libzip B, libjava A+B, libjvm A+B.
set -u
A=/home/user/Tutorial/EchoTrace/ablation
T=$A/tomcat_11.0.22
S=$T/run_targets; mkdir -p "$S"
GUARD="${GUARD:-pause}"; KILL_BELOW="${KILL_BELOW:-20}"; MAX_REQUEUE="${MAX_REQUEUE:-2}"

avail() { awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo; }
descendants() {   # every process below $1
    local c
    for c in $(ps -o pid= --ppid "$1"); do echo "$c"; descendants "$c"; done
}
my_syspart() { for p in $(descendants "$1"); do [ "$(ps -o comm= -p "$p" 2>/dev/null)" = syspart ] && echo "$p"; done; }

run() {   # lib arms min_available_gb cap_gb timeout_s targets_file
    local lib=$1 arms=$2 gate=$3 cap=$4 limit=$5 targets=$S/target_$1.tsv
    local pid stopped m killed rss_stopped r p tries=0 v
    grep -P "^$lib\t" "$6" > "$targets"
    while :; do
        until [ "$(avail)" -ge "$gate" ]; do sleep 60; done
        echo "START $lib arms=$arms (available $(avail) GB, cap $cap GB, timeout $limit s, guard $GUARD) $(date +%H:%M)"
        ( cd "$A" && RESULTS=/home/user/Tutorial/EchoTrace_latest/Final_results_latest_versions/tomcat_11.0.22 \
            SYMBOLIZED=1 SYSPART_APP=/home/user/SysPartCode/analysis/app TARGETS="$targets" ARMS="$arms" \
            NICE=${NICE:-10} JOB_MEM_GB=$cap JOB_TIMEOUT=$limit LEAN=1 ./run_ablation.sh tomcat_11.0.22 1 | grep --line-buffered '^G ' ) &
        pid=$!; stopped=0; killed=0; rss_stopped=0
        while kill -0 "$pid" 2>/dev/null; do
            m=$(avail)
            if [ -n "${RSS_STOP_GB:-}" ] && [ "$rss_stopped" = 0 ]; then
                for p in $(my_syspart "$pid"); do
                    r=$(ps -o rss= -p "$p" 2>/dev/null) || continue
                    if [ "${r:-0}" -gt $(( RSS_STOP_GB * 1048576 )) ]; then
                        kill -STOP "$p"; rss_stopped=1
                        echo "RSS-STOP $lib: syspart $p at $(( r / 1048576 )) GB resident, stopped; kill -CONT $p to resume $(date +%H:%M)"
                    fi
                done
            fi
            if [ "$GUARD" = kill ] && [ "$m" -lt "$KILL_BELOW" ]; then
                kill -KILL $(descendants "$pid") "$pid" 2>/dev/null
                killed=1; echo "KILLED $lib: available $m GB $(date +%H:%M)"
                break
            fi
            if [ "$GUARD" = pause ]; then
                if [ "$stopped" = 0 ] && [ "$m" -lt 15 ]; then
                    stopped=1; echo "PAUSED $lib: available $m GB $(date +%H:%M)"
                elif [ "$stopped" = 1 ] && [ "$m" -gt 30 ]; then
                    for p in $(my_syspart "$pid"); do kill -CONT "$p"; done
                    stopped=0; echo "RESUMED $lib: available $m GB $(date +%H:%M)"
                fi
                # Re-applied each round: a later SysPart step may start while paused.
                if [ "$stopped" = 1 ]; then
                    for p in $(my_syspart "$pid"); do kill -STOP "$p"; done
                fi
            fi
            sleep 10
        done
        wait "$pid" 2>/dev/null
        if [ "$killed" = 0 ]; then
            echo "END $lib $(date +%H:%M)"
            return 0
        fi
        # A killed run never reached its own cleanup: drop partial results.
        for v in $arms; do rm -f "$T/$v/$lib/syscalls.txt" "$T/$v/$lib/callgraph_a23.txt.zst"; done
        tries=$((tries + 1))
        if [ "$tries" -gt "$MAX_REQUEUE" ]; then
            echo "HOLD $lib: killed $tries times; queue stopped $(date +%H:%M)"
            return 1
        fi
        echo "REQUEUE $lib ($tries of $MAX_REQUEUE) $(date +%H:%M)"
    done
}

# Gate, cap and time limit per library: the JDK ones load all of libjvm.
entry() {   # lib arms
    case "$1" in
        libjvm.so) run "$1" "$2" "${GATE:-40}" "${JVM_CAP:-35}" 10800 "$T/targets_libjvm.tsv" ;;
        *)         run "$1" "$2" "${GATE:-40}" 32 7200 "$T/targets_jdk3.tsv" ;;
    esac
}

[ $# -gt 0 ] || set -- "libnet.so:B" "libzip.so:B" "libjava.so:A B" "libjvm.so:A B"
for e in "$@"; do
    entry "${e%%:*}" "${e#*:}" || exit 1
done
echo "ALL DONE"
