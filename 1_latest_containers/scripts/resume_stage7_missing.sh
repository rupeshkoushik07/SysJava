#!/bin/bash
# Resume a target whose stage 7 (SysPart on mapped libraries and executed
# binaries) was interrupted, then continue the pipeline from stage 8.
#
# automate_syscall_analysis.sh has no skip-complete, so rerunning stage 7 would
# redo every library. Instead this reruns only the items without a finished
# result (callgraph.json plus a non-empty syscalls.txt): missing libraries via a
# start-function directory holding just their start files (same relative paths,
# so find_binary_file still resolves JDK*_LIBS/ subpaths), and the executables
# when any of them is missing (all-or-nothing, as automate offers no per-binary
# selection; finished binaries are few and cheap).
#
# Usage: scripts/resume_stage7_missing.sh <target>   (run from the repo root)
set -euo pipefail

T="$1"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
WS="${REPO}/workspaces/${T}"
SYM="${REPO}/Final_results_latest_versions/${T}/Dataset_symbolized"
SLIBS="${SYM}/LIBS_${T}"
SBINS="${SYM}/BINARIES_${T}"
OUTPUTS_DIR="${WS}/outputs_${T}"
LIB_OUT="${WS}/syscalls_output_${T}"
BIN_OUT="${WS}/syscalls_BIN_${T}"
RESUME_DIR="${WS}/outputs_${T}_stage7_resume"

done_result() { [ -f "$1/callgraph.json" ] && [ -s "$1/syscalls.txt" ]; }

rm -rf "$RESUME_DIR"
mkdir -p "$RESUME_DIR"
missing_libs=0
while IFS= read -r sf; do
    rel="${sf#"$OUTPUTS_DIR"/}"
    name="$(basename "$sf" .txt)"
    if ! done_result "${LIB_OUT}/${name}"; then
        mkdir -p "$(dirname "${RESUME_DIR}/${rel}")"
        cp "$sf" "${RESUME_DIR}/${rel}"
        missing_libs=$((missing_libs + 1))
        echo "resume: library ${rel%.txt}"
    fi
done < <(find "$OUTPUTS_DIR" \( -name "*.so.txt" -o -name "*.so.[0-9]*.txt" \) -type f | sort)

missing_bins=0
for b in "$SBINS"/*; do
    [ -f "$b" ] && [ -x "$b" ] || continue
    done_result "${BIN_OUT}/$(basename "$b")" || missing_bins=$((missing_bins + 1))
done
echo "resume ${T}: ${missing_libs} libraries and ${missing_bins} binaries without a finished result"

args=(--binary-dir "$SLIBS" --startfunc-dir "$RESUME_DIR" --output-dir "$LIB_OUT" --img-name "$T" --log)
[ "$missing_libs" -eq 0 ] && args+=(--binaries-only)
[ "$missing_bins" -gt 0 ] && args+=(--binaries-dir "$SBINS")

if [ "$missing_libs" -gt 0 ] || [ "$missing_bins" -gt 0 ]; then
    cd "$WS"
    ulimit -s 1048576  # Egalito recursion depth on a full libjvm
    bash "${WS}/scripts/automate_syscall_analysis.sh" "${args[@]}" \
        || echo "resume ${T}: automate_syscall_analysis exited $? (per-item failures, e.g. gosu, are listed above); continuing"
fi

cd "$REPO"
exec bash scripts/run_latest_target.sh "$T" 8
