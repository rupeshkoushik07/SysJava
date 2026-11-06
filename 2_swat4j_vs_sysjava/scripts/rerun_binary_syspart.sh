#!/usr/bin/env bash
#
# Rerun SysPart on one executable of a finished JDK 8 target, in place, with a
# memory cap and a time limit (used for the _start + main reruns).
#
#   scripts/rerun_binary_syspart.sh <target> <binary> [start ...]
#
# The default starts are _start, plus main when the binary has a main symbol.
# The result folder is the one organize_results.sh left in the workspace
# (jdk8_workspaces/<target>/Final_results/<target>/Binary_Analysis/...), so a
# following `run_jdk8_target.sh <target> 9` merges it. The previous folder is
# kept as Final_results_JDK8/_before_rerun/<target>/<binary>/ first.
#   SYSPART_VMEM_LIMIT_KB  ulimit -v for SysPart (default 32 GB)
#   SYSPART_RERUN_TIMEOUT  seconds for the whole run (default 7200)
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
T="${1:?target required}"; B="${2:?binary required}"; shift 2
WS="${REPO}/jdk8_workspaces/${T}"
D="${WS}/Final_results/${T}/Binary_Analysis/syscalls_BIN_${T}/${B}"
BIN="${REPO}/Final_results_JDK8/${T}/Dataset_symbolized/BINARIES_${T}/${B}"
[ -d "$D" ] && [ -f "$BIN" ] || { echo "no result folder or binary for ${T}/${B}" >&2; exit 1; }

KEEP="${REPO}/Final_results_JDK8/_before_rerun/${T}/${B}"
[ -e "$KEEP" ] || { mkdir -p "$(dirname "$KEEP")"; cp -a "$D" "$KEEP"; }

if [ $# -gt 0 ]; then
    printf '%s\n' "$@" > "$D/start.txt"
else
    echo _start > "$D/start.txt"
    { nm "$BIN" 2>/dev/null; nm -D "$BIN" 2>/dev/null; } | grep -q " [Tt] main$" && echo main >> "$D/start.txt"
fi
rm -f "$D/syspart_failed.txt" "$D/excluded_starts_syspart_crash.txt"

# Same library search path automate_syscall_analysis.sh builds for this target.
ULP=$(grep -o 'USER_LIBRARY_PATH="[^"]*"' "${REPO}/Final_results_JDK8/${T}/pipeline_run.log" | tail -1 | cut -d'"' -f2)
cd "${WS}/SysPartCode/analysis/app"
USER_LIBRARY_PATH="$ULP" SYSPART_VMEM_LIMIT_KB="${SYSPART_VMEM_LIMIT_KB:-33554432}" \
    timeout -k 60 "${SYSPART_RERUN_TIMEOUT:-7200}" \
    src/scripts/compute_syscalls.sh "$BIN" "$D" "$D/start.txt" --log > "$D/logfile.txt" 2>&1 && rc=0 || rc=$?
echo "${T}/${B}: exit=${rc} starts=$(tr '\n' ' ' < "$D/start.txt")syscalls=$(grep -c . "$D/syscalls.txt" 2>/dev/null || echo none)"
exit $rc
