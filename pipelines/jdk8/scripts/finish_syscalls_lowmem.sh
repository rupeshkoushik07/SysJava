#!/usr/bin/env bash
#
# Complete a SysPart result directory whose call graph was written but whose
# final syscall step died (getsyscalls.py ran out of memory on a full libjvm
# graph). Repeats only the last two steps of compute_syscalls.sh, with the
# low-memory getsyscalls, so SysPart itself does not have to run again.
#
# Usage: scripts/finish_syscalls_lowmem.sh <result-dir> [...]
#   Each dir needs allfunctions.txt, syscalls_with_callsites.txt,
#   callgraph.json (non-empty) and start.txt.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for out in "$@"; do
    out="${out%/}"
    if ! grep -q '"id"' "${out}/callgraph.json" 2>/dev/null || [ ! -s "${out}/allfunctions.txt" ] \
        || [ ! -s "${out}/start.txt" ]; then
        echo "SKIP ${out}: no usable call graph" >&2
        continue
    fi
    # Same start-function resolution as compute_syscalls.sh.
    : > "${out}/startfuncs_with_addr.txt"
    while read -r start_func; do
        addr=$(awk -v fname="$start_func" '$1 == fname {print $2}' "${out}/allfunctions.txt")
        [ -n "$addr" ] && echo "${start_func}_${addr}" >> "${out}/startfuncs_with_addr.txt"
    done < "${out}/start.txt"
    python3 "${SCRIPT_DIR}/getsyscalls_lowmem.py" "${out}/callgraph.json" "${out}/syscalls_with_callsites.txt" \
        "${out}/startfuncs_with_addr.txt" --log "${out}/logfile.txt" > "${out}/syscalls.txt"
    printf '%s\tfinished\tfunctions=%s\tfuzzy=%s\tsyscalls=%s\n' "$out" \
        "$(wc -l < "${out}/allfunctions.txt")" "$(grep -c '^fuzzyfunc' "${out}/allfunctions.txt" || true)" \
        "$(wc -l < "${out}/syscalls.txt")"
done
