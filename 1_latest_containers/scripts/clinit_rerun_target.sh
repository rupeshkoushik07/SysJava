#!/bin/bash
# Static-initializer (clinit) fix rerun of an already-finished target (user decision 2026-11-05),
# into Final_results_latest_versions_clinit/<t>, leaving Final_results_latest_versions/<t> untouched
# as the unfixed baseline. Reuses the baseline's capture, datasets, debug symbols, binaries and
# unchanged libraries; reruns SysPart only for libraries whose start-function list changed (each
# with its full new list).
#
#   A  workspace workspaces_clinit/<t>: scripts copy, links to the baseline Dataset/sysdig outputs
#   B  stages 4-5 with the patched detector (DETECTOR_REPO, 52628c4), via run_latest_target.sh
#   C  diff every library start list against the baseline -> FINAL/clinit_startfunc_diff.tsv
#   D  stage 7: copy unchanged libraries' results + all binaries' results; SysPart for changed/new
#   E  stage 8 seeded with the baseline's stage-8 results (skip-complete), then drop stage-8 results
#      for libraries that are now JNI-mapped (they are analysed in stage 7 instead)
#   F  stages 9-11 (merge with the current runc.txt, seccomp runtime test)
#
# Usage (repo root): scripts/clinit_rerun_target.sh <target>
set -euo pipefail
T="$1"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
export WS_ROOT="${REPO}/workspaces_clinit" RESULTS_ROOT="${REPO}/Final_results_latest_versions_clinit"
export DETECTOR_REPO=/home/user/Tutorial/EchoTrace_clinit_build
W="${WS_ROOT}/${T}"; F="${RESULTS_ROOT}/${T}"; B="${REPO}/Final_results_latest_versions/${T}"
[ -d "$B/Binary_Analysis" ] || { echo "baseline $B incomplete" >&2; exit 1; }
say() { echo "$(date +%T) [clinit ${T}] $*"; }

# A ------------------------------------------------------------------------------------------
say "A: workspace $W, results $F"
mkdir -p "$W" "$F"
rm -rf "$W/scripts"; cp -a "${REPO}/scripts" "$W/scripts"
ln -sfn "${REPO}/SysPartCode" "$W/SysPartCode"
cp "${REPO}/runc.txt" "$W/runc.txt"
for d in JARFILES LIBS BINARIES RUNTIME; do ln -sfn "$B/Dataset/${d}_${T}" "$W/${d}_${T}"; done
ln -sfn "$B/Dynamic_Analysis/sysdig_outputs_${T}" "$W/sysdig_outputs_${T}"
ln -sfn "$B/Dataset" "$F/Dataset"
ln -sfn "$B/Dataset_symbolized" "$F/Dataset_symbolized"
printf 'baseline=%s\nreused: capture, Dataset, Dataset_symbolized, binaries, unchanged libraries\n' "$B" > "$F/clinit_rerun_provenance.txt"

# B ------------------------------------------------------------------------------------------
say "B: stages 4-5 with $(git -C "$DETECTOR_REPO" rev-parse --short HEAD)"
rm -rf "$W/outputs_${T}"
LAST_STAGE=5 bash "${REPO}/scripts/run_latest_target.sh" "$T" 4

# C ------------------------------------------------------------------------------------------
NEW="$W/outputs_${T}"; OLD="$B/Bytecode_Analysis/outputs_${T}"
DIFF="$F/clinit_startfunc_diff.tsv"
python3 - "$OLD" "$NEW" "$DIFF" <<'EOF'
import sys, pathlib
old, new, out = map(pathlib.Path, sys.argv[1:])
def libs(root):
    return {str(p.relative_to(root)): {l.strip() for l in p.read_text(errors="replace").splitlines() if l.strip()}
            for p in root.rglob("*.txt") if ".so" in p.name and "excluded" not in str(p.relative_to(root))}
o, n = libs(old), libs(new)
with out.open("w") as fh:
    fh.write("start_file\tstatus\told_starts\tnew_starts\tadded\tremoved\n")
    for k in sorted(o.keys() | n.keys()):
        a, b = o.get(k), n.get(k)
        st = "new" if a is None else "removed" if b is None else "unchanged" if a == b else "changed"
        fh.write(f"{k}\t{st}\t{len(a or ())}\t{len(b or ())}\t{len((b or set()) - (a or set()))}\t{len((a or set()) - (b or set()))}\n")
EOF
say "C: start-list diff:"; column -t "$DIFF" | sed 's/^/    /'

# D ------------------------------------------------------------------------------------------
LIB_OUT="$W/syscalls_output_${T}"; rm -rf "$LIB_OUT" "$W/syscalls_BIN_${T}"; mkdir -p "$LIB_OUT"
cp -a "$B/Binary_Analysis/syscalls_BIN_${T}" "$W/syscalls_BIN_${T}"
RERUN_SF="$W/outputs_${T}_clinit_changed"; rm -rf "$RERUN_SF"; mkdir -p "$RERUN_SF"
n_rerun=0
while IFS=$'\t' read -r rel st _; do
    [ "$st" = start_file ] && continue
    name="$(basename "$rel" .txt)"
    case "$st" in
        unchanged)
            [ -d "$LIB_OUT/$name" ] || cp -a "$B/Binary_Analysis/syscalls_output_${T}/$name" "$LIB_OUT/$name" ;;
        changed|new)
            mkdir -p "$(dirname "$RERUN_SF/$rel")"; cp "$NEW/$rel" "$RERUN_SF/$rel"; n_rerun=$((n_rerun + 1)) ;;
    esac
done < "$DIFF"
# A library listed both as LIBS_/x.so and JDK*_LIBS/x.so shares one output dir: if either copy
# changed, its directory is rerun, so drop a copied "unchanged" twin first.
for sf in $(find "$RERUN_SF" -name '*.txt'); do rm -rf "$LIB_OUT/$(basename "$sf" .txt)"; done
say "D: stage 7 for ${n_rerun} changed/new start file(s); unchanged libraries and binaries copied"
if [ "$n_rerun" -gt 0 ]; then
    EMPTY="$W/.no_binaries"; mkdir -p "$EMPTY"
    (cd "$W" && ulimit -s 1048576 && bash "$W/scripts/automate_syscall_analysis.sh" \
        --binary-dir "$B/Dataset_symbolized/LIBS_${T}" --binaries-dir "$EMPTY" --startfunc-dir "$RERUN_SF" \
        --output-dir "$LIB_OUT" --img-name "$T" --log) \
        || say "D: automate_syscall_analysis exited $? (per-item failures listed above); continuing"
fi

# E ------------------------------------------------------------------------------------------
rm -rf "$W/syscalls_unanalysed_${T}" "$W/startfuncs_unanalysed_${T}" "$W/jna_ffi_analysis"
cp -a "$B/Binary_Analysis/syscalls_unanalysed_${T}" "$W/syscalls_unanalysed_${T}"
cp -a "$B/Binary_Analysis/startfuncs_unanalysed_${T}" "$W/startfuncs_unanalysed_${T}"
say "E: stage 8 (seeded with baseline stage-8 results)"
LAST_STAGE=8 bash "${REPO}/scripts/run_latest_target.sh" "$T" 8
for d in "$W/syscalls_unanalysed_${T}"/*/; do
    n="$(basename "$d")"
    if [ -d "$LIB_OUT/$n" ]; then
        mkdir -p "$W/.superseded_unanalysed"; mv "$d" "$W/.superseded_unanalysed/$n"
        say "E: $n is now JNI-mapped; its stage-8 result is superseded by stage 7"
    fi
done

# F ------------------------------------------------------------------------------------------
say "F: stages 9-11"
bash "${REPO}/scripts/run_latest_target.sh" "$T" 9
say "done: $(grep -h 'RESULT=' "$F/seccomp_runtime_test.log" | tail -1)"
