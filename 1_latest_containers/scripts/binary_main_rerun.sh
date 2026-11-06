#!/bin/bash
# Executable start-function correction for a finished target (user decision 2026-11-05 ~22:00):
# starts = _start + main for dynamically linked executables (+ uu_<tool>::uumain for uutils
# multi-call binaries), exactly as automate_syscall_analysis.sh's write_start_entries now does for
# new runs. Non-PIE _start passes main to __libc_start_main as an absolute immediate that SysPart
# does not follow, so those binaries only got libc's startup syscalls. Reruns the listed binaries,
# keeps the old results as *_before_main (a component that is not rerun keeps its exact syscalls),
# then reruns stages 9-11.
#
# Usage (repo root): scripts/binary_main_rerun.sh <target> <results_root> <ws_root> <binary>...
set -euo pipefail
T="$1"; RR="$(realpath "$2")"; WR="$(realpath "$3")"; shift 3; TOOLS=("$@")
REPO="$(cd "$(dirname "$0")/.." && pwd)"
W="$WR/$T"; F="$RR/$T"
SLIBS="$F/Dataset_symbolized/LIBS_$T"; SBINS="$F/Dataset_symbolized/BINARIES_$T"
say() { echo "$(date +%T) [main $T] $*"; }
log_message() { :; }  # automate's logger needs its own globals; not wanted here
source <(sed -n '/^write_start_entries() {/,/^}/p' "$REPO/scripts/automate_syscall_analysis.sh")
[ -d "$F/Binary_Analysis/syscalls_BIN_$T" ] || { say "no finished Binary_Analysis in $F"; exit 1; }

# 1. baseline copies
# Never overwrite an existing *_before_main: on a repeat run it is the true pre-fix state.
if [ ! -d "$F/Binary_Analysis_before_main" ]; then
    cp -a "$F/Binary_Analysis" "$F/Binary_Analysis_before_main"
    cp "$F/seccomp_runtime_test.log" "$F/seccomp_runtime_test_before_main.log"
    cp "$F/named_callgraph_summary.tsv" "$F/named_callgraph_summary_before_main.tsv"
fi

# 2. undo organize_results.sh (stage 10 moved the workspace folders into Final_results/<t>/<group>/)
O=$W/Final_results/$T
for g in Dataset Bytecode_Analysis Dynamic_Analysis Binary_Analysis; do
    [ -d "$O/$g" ] || continue
    for d in "$O/$g"/*; do [ -e "$d" ] && { rm -rf "$W/$(basename "$d")"; mv "$d" "$W/"; }; done
done
rm -rf "$W/Final_results"
# The workspace copy can be older than the published results (e.g. orientdb's glibc-2.43 cancel-site
# recompute was applied to Final_results_latest_versions only), so every syscalls_*/startfuncs_*/jna_ffi
# component is restored from the published pre-fix copy: what is not rerun keeps its exact syscalls.
for d in "$F/Binary_Analysis_before_main"/*; do
    rm -rf "$W/$(basename "$d")"; cp -a "$d" "$W/$(basename "$d")"
done

# 3. per-tool rerun (USER_LIBRARY_PATH as automate_syscall_analysis.sh builds it)
ULP="$SLIBS"; for d in $(find "$SLIBS" -maxdepth 1 -type d -name 'JDK*_LIBS' | sort); do ULP="$ULP:$d"; for s in $(find "$d" -mindepth 1 -type d | sort); do ULP="$ULP:$s"; done; done
for tool in "${TOOLS[@]}"; do
    O=$W/syscalls_BIN_$T/$tool; N=$O.main
    rm -rf "$N"; mkdir -p "$N"; write_start_entries "$SBINS/$tool" "$N/start.txt" 2>/dev/null
    grep -qx main "$N/start.txt" || { say "$tool: no main (no main symbol), left as is"; rm -rf "$N"; continue; }
    # Hard cap (coordinator, 2026-11-05: storm python3.14 from main exceeded 96 GB): 32 GB virtual
    # memory and 2 h per binary; a capped binary keeps its previous result.
    (cd "$W/SysPartCode/analysis/app" && ulimit -s 1048576 && ulimit -v "${BINARY_RERUN_VMEM_KB:-33554432}" \
        && USER_LIBRARY_PATH="$ULP" timeout -k 30 "${BINARY_RERUN_TIMEOUT:-7200}" \
        bash src/scripts/compute_syscalls.sh "$SBINS/$tool" "$N" "$N/start.txt" --log) > "$N/run.log" 2>&1 \
        || { say "$tool: rerun failed, keeping _start-only result; see $N/run.log"; continue; }
    old=$(wc -l < "$O/syscalls.txt")
    added=$(comm -13 <(sort "$O/syscalls.txt") <(sort "$N/syscalls.txt") | tr '\n' ' ')
    mkdir -p "$W/.before_main"; rm -rf "$W/.before_main/$tool"; mv "$O" "$W/.before_main/$tool"; mv "$N" "$O"
    say "$tool: starts $(grep -c . "$O/startfuncs_with_addr.txt"), syscalls $old -> $(wc -l < "$O/syscalls.txt") (+${added})"
done
cat >> "$SBINS/ADDED_first_start_binaries.md" <<NOTE

# Executables: _start + main start functions ($(date '+%F %H:%M'))

${T}: ${TOOLS[*]} were rerun with starts \`_start\` + \`main\` (plus \`uu_<tool>::uumain\` for uutils
multi-call binaries), the rule automate_syscall_analysis.sh now applies to every dynamically linked
executable. In non-PIE binaries _start hands main to __libc_start_main as an absolute immediate that
SysPart does not follow, so analysed from \`_start\` alone they only got libc's startup syscalls.
Previous results are kept in Binary_Analysis_before_main/.
NOTE
cp "$SBINS/ADDED_first_start_binaries.md" "$W/syscalls_BIN_$T/" 2>/dev/null || true

# 4. stages 9-11 into the same results/workspace roots
WS_ROOT="$WR" RESULTS_ROOT="$RR" bash "$REPO/scripts/run_latest_target.sh" "$T" 9
say "done: $(grep -h RESULT= "$F/seccomp_runtime_test.log" | tail -1)"
