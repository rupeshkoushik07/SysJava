#!/bin/bash
# SWAT4J dynamic analysis as described in the paper (SANER'24, Sec. IV-C / V-B):
# attach `strace -c` to Docker's containerd, start the container, stop once startup is done.
# The paper reports startup traces of 8.36s-45.85s; we stop at the app's "ready" log line,
# or when the container exits, capped at MAX_WAIT seconds (slow hosts need more than 45s).
#
# Usage: dynamic_swat4j.sh [app ...]   (default: all 10 SWAT4J apps)
# Output: dynamic/<app>_strace.txt (raw strace -c table), dynamic/<app>_result.txt (names),
#         dynamic/<app>.log (container log), dynamic/timing.csv
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/dynamic"
MAX_WAIT="${MAX_WAIT:-180}"
mkdir -p "$OUT"

# Docker's containerd (the one dockerd's --containerd socket points at), not kind's
CONTAINERD_PID="$(pgrep -x containerd | while read -r p; do
  [ "$(sudo readlink /proc/$p/ns/mnt)" = "$(sudo readlink /proc/1/ns/mnt)" ] && echo "$p"; done | head -1)"

# app | image | extra docker args | readiness regex in container log
# CPU_IDLE: no log output to wait for (irb blocks on a terminal query), so startup is done
# once the container has used CPU and then sits idle for two consecutive samples
APPS="
tomcat|tomcat:7.0||Server startup in
jetty|jetty:9.4.51||Started @
orientdb|orientdb:3.2.19|-e ORIENTDB_ROOT_PASSWORD=root|OrientDB Studio available
cassandra|cassandra:3.0.29||Starting listening for CQL clients
elasticsearch|elasticsearch:7.5.2|-e discovery.type=single-node|message.: .started
solr|solr:8.7.0||Server Started @
zookeeper|zookeeper:3.4.14||binding to port
storm|storm:2.4.0||no default daemon: runs until exit
groovy|groovy:4.0.0||for help
jruby|jruby:9.4.2.0||CPU_IDLE
"

[ -f "$OUT/timing.csv" ] || echo "app,image,seconds,stopped_by,syscalls" > "$OUT/timing.csv"

run_app() {
  local app="$1" image="$2" args="$3" ready="$4"
  local name="swat4j_dyn_$app" raw="$OUT/${app}_strace.txt"
  docker rm -f "$name" >/dev/null 2>&1

  sudo strace -f -c -o "$raw" -p "$CONTAINERD_PID" 2>/dev/null &
  local spid=$!
  sleep 2   # let strace attach to all containerd threads

  local t0 stopped_by="timeout" busy=0 idle=0
  t0=$(date +%s.%N)
  # -it keeps interactive images (groovysh, irb) alive; servers ignore it
  # shellcheck disable=SC2086
  docker run -dit --name "$name" $args "$image" >/dev/null
  while :; do
    local el
    el=$(echo "$(date +%s.%N) - $t0" | bc)
    if [ "$ready" = "CPU_IDLE" ]; then
      local cpu; cpu=$(docker stats --no-stream --format '{{.CPUPerc}}' "$name" 2>/dev/null | tr -d '%')
      if [ -n "$cpu" ] && (( $(echo "$cpu > 5" | bc) )); then busy=1; idle=0
      elif [ "${busy:-0}" = 1 ] && [ -n "$cpu" ] && (( $(echo "$cpu < 1" | bc) )); then idle=$((idle + 1)); fi
      if [ "${idle:-0}" -ge 2 ]; then stopped_by="ready"; break; fi
    elif docker logs "$name" 2>&1 | grep -qE "$ready"; then stopped_by="ready"; break; fi
    if [ "$(docker inspect -f '{{.State.Running}}' "$name" 2>/dev/null)" != "true" ]; then stopped_by="exited"; break; fi
    if (( $(echo "$el >= $MAX_WAIT" | bc) )); then break; fi
    sleep 0.5
  done
  local secs
  secs=$(printf '%.2f' "$(echo "$(date +%s.%N) - $t0" | bc)")

  # stop tracing before teardown so container removal is not counted
  sudo pkill -INT -P "$spid" strace 2>/dev/null || sudo kill -INT "$spid" 2>/dev/null
  wait "$spid" 2>/dev/null
  docker logs "$name" > "$OUT/$app.log" 2>&1
  docker rm -f "$name" >/dev/null 2>&1
  sudo chown "$(id -u):$(id -g)" "$raw"

  # strace -c rows end in the syscall name; skip header, separator and total lines
  awk '$NF ~ /^[a-z_0-9]+$/ && $NF != "total" && $NF != "syscall" {print $NF}' "$raw" | sort -u > "$OUT/${app}_result.txt"
  local n; n=$(wc -l < "$OUT/${app}_result.txt")
  echo "$app,$image,$secs,$stopped_by,$n" >> "$OUT/timing.csv"
  echo "[done] $app: ${secs}s ($stopped_by), $n syscalls"
}

echo "Tracing containerd PID $CONTAINERD_PID, cap ${MAX_WAIT}s"
want=" $* "
while IFS='|' read -r app image args ready; do
  [ -z "$app" ] && continue
  [ $# -gt 0 ] && [[ "$want" != *" $app "* ]] && continue
  run_app "$app" "$image" "$args" "$ready"
done <<< "$APPS"
