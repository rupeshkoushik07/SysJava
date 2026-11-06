#!/bin/bash
# Does the binding result depend on the start set the call graph is built from?
# Builds libssl.so.3's call graph from the binding start functions only (B),
# with the same SysPart build and the same lean BFS as the ablation, and
# compares with B/libssl.so.3/syscalls.txt, which is the BFS from the same
# start functions over the graph rooted at every function (A).
# Limits agreed with the Manager session: nice 10, 12 GB cap, start only with
# >= 25 GB available, SIGSTOP below 15 GB and SIGCONT above 30 GB.
set -u
T=/home/user/Tutorial/EchoTrace/ablation/tomcat_11.0.22
V=$T/validation/libssl_binding_only
L=/home/user/Tutorial/EchoTrace_latest/Final_results_latest_versions/tomcat_11.0.22/Dataset_symbolized/LIBS_tomcat_11.0.22
mkdir -p "$V"
export USER_LIBRARY_PATH="$L:$(find "$L" -type d | sort | paste -sd:)"
avail() { awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo; }

until [ "$(avail)" -ge 25 ]; do sleep 30; done
echo "START (available $(avail) GB) $(date +%H:%M)"
(
    set -eo pipefail
    ulimit -v $(( 12 * 1048576 ))
    cd /home/user/SysPartCode/analysis/app
    nice -n 10 timeout 3600 ./syspart -p "$L/libssl.so.3" -s "$T/starts/B/libssl.so.3.txt" -i -a 23 \
        | zstd -q -T1 -f -o "$V/callgraph_a23.txt.zst"
    zstdcat "$V/callgraph_a23.txt.zst" \
        | python3 /home/user/Tutorial/EchoTrace/ablation/lean_syscalls.py - \
            "$T/B/libssl.so.3/syscalls_with_callsites.txt" "$T/B/libssl.so.3/startfuncs_with_addr.txt" \
        | sort -u > "$V/syscalls.txt"
) > "$V/run.log" 2>&1 &
pid=$!
stopped=0
while kill -0 "$pid" 2>/dev/null; do
    m=$(avail)
    sp=$(pgrep -f "syspart -p $L/libssl.so.3 -s $T/starts/B/libssl.so.3.txt" || true)
    if [ "$stopped" = 0 ] && [ "$m" -lt 15 ]; then stopped=1; echo "PAUSED (available $m GB) $(date +%H:%M)"; fi
    if [ "$stopped" = 1 ] && [ "$m" -gt 30 ]; then
        [ -z "$sp" ] || kill -CONT $sp; stopped=0; echo "RESUMED (available $m GB) $(date +%H:%M)"
    fi
    [ "$stopped" = 0 ] || [ -z "$sp" ] || kill -STOP $sp
    sleep 15
done
wait "$pid"; rc=$?
echo "END rc=$rc $(date +%H:%M)"
if [ "$rc" = 0 ]; then
    echo "binding-only graph: $(wc -l < "$V/syscalls.txt") syscalls; all-roots graph (B/): $(wc -l < "$T/B/libssl.so.3/syscalls.txt")"
    echo "only in all-roots graph: $(comm -13 "$V/syscalls.txt" <(sort -u "$T/B/libssl.so.3/syscalls.txt") | tr '\n' ' ')"
    echo "only in binding-only graph: $(comm -23 "$V/syscalls.txt" <(sort -u "$T/B/libssl.so.3/syscalls.txt") | tr '\n' ' ')"
fi
