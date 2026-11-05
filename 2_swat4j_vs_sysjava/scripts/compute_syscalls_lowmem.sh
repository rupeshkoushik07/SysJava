#!/bin/bash
# Copy of SysPartCode/analysis/app/src/scripts/compute_syscalls.sh that streams the
# call graph through scripts/parse_callgraph_to_json_lowmem.py (same JSON, ~8x less
# memory) and computes reachable syscalls with scripts/getsyscalls_lowmem.py (same
# result, ~50x less memory). Run from SysPartCode/analysis/app, like the original.

show_help() {
    cat << EOF
Usage: $0 arg1 arg2 arg3 [--log]

Arguments:
  arg1    ELF binary to be analysed
  arg2    Folder to store outputs
  arg3    Path to a file containing one or more start functions (one per line)

Options:
  --log   This will log the paths to the system calls from the start functions in logfile.txt in the output folder
  -h, --help
          Show this help message and exit

Outputs:
  syscalls.txt			List of system calls reachable from the start functions
  callgraph.txt			Callgraph of the ELF binary and its libraries
  syscalls_with_callsites.txt	The functions within the call graph where system calls are invoked
  allfunctions.txt		List of all functions in ELF binary and its libraries along with their addresses
  logfile.txt			Contains paths to the system calls from the start functions
EOF
}

if [[ $# -lt 3 || "$1" == "-h" || "$1" == "--help" ]]; then
    show_help
    exit 0
fi

APP=$1
OUT=$(realpath $2)
STARTFILE=$(realpath $3)
shift 3

log_flag=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --log) log_flag=true ;;
    esac
    shift
done

# Stripped static (or static-PIE) executables such as ldconfig cannot be
# unstripped with eu-unstrip; Egalito reads their debug file from
# <sysroot>/usr/lib/debug/.build-id instead, so point it at the symbol pool.
if [ -z "${EGALITO_SYSROOT:-}" ] && ! readelf -l "$APP" 2>/dev/null | grep -q 'INTERP' \
        && { readelf -h "$APP" 2>/dev/null | grep -q 'EXEC'; \
             readelf -d "$APP" 2>/dev/null | grep -q 'FLAGS_1.*PIE'; }; then
    export EGALITO_SYSROOT="$(dirname "$(realpath "$0")")/../artifacts/all-running-containers/debug-symbols"
fi

temp_start_func=$(head -1 $STARTFILE)
./syspart -p $APP -s $temp_start_func -a 25 > $OUT/allfunctions.txt
./syspart -p $APP -s $temp_start_func -a 24 > $OUT/syscalls_with_callsites.txt
# Symbolized libraries list versioned exports as name@@VERSION (from .symtab), so
# a plain start name like "crypt" no longer matches. Resolve each start name to
# its versioned spelling from allfunctions.txt; names already present stay as is.
RESOLVED_START="${OUT}/startfuncs_resolved.txt"
awk 'NR==FNR { n=$1; sub(/@.*/, "", n); if ($1 ~ /@/ && !(n in ver)) ver[n]=$1; have[$1]=1; next }
     { print (($1 in have) || !($1 in ver)) ? $1 : ver[$1] }' "$OUT/allfunctions.txt" "$STARTFILE" > "$RESOLVED_START"
./syspart -p $APP -s $RESOLVED_START -i -a 23 | python3 "$(dirname "$(realpath "$0")")/parse_callgraph_to_json_lowmem.py" - $OUT/callgraph.json
# A SysPart crash here (e.g. SIGSEGV on libgcrypt) leaves an empty call graph and would be
# reported as "completed, 0 syscalls"; fail instead so it is counted as a failed result.
callgraph_status=("${PIPESTATUS[@]}")

# Some start functions crash SysPart on their own (libsystemd's sd_bus_add_fallback).
# Rule: exclude only those, analyse the rest. Bisect the start list with the call-graph
# step alone, record every crashing start with its exit code in
# excluded_starts_syspart_crash.txt, and rebuild the call graph from the remaining starts.
# SYSPART_EXCLUDE_CRASHES=0 disables this; SYSPART_BISECT_MAX_RUNS bounds the search.
EXCLUDED="${OUT}/excluded_starts_syspart_crash.txt"
rm -f "$EXCLUDED"
if [ "${callgraph_status[0]}" -ne 0 ] && [ "${SYSPART_EXCLUDE_CRASHES:-1}" != 0 ] \
        && [ "$(grep -c . "$RESOLVED_START")" -gt 1 ]; then
    echo "compute_syscalls: call-graph step exited ${callgraph_status[0]}; searching for start functions that crash SysPart" >&2
    work=$(mktemp -d)
    runs=0
    max_runs=${SYSPART_BISECT_MAX_RUNS:-60}
    cg_ok() { runs=$((runs + 1)); ./syspart -p $APP -s "$1" -i -a 23 > /dev/null 2>&1; }
    : > "$work/bad"
    while [ "$runs" -lt "$max_runs" ]; do
        grep -vxFf "$work/bad" "$RESOLVED_START" > "$work/rest" || true
        [ -s "$work/rest" ] || break
        cg_ok "$work/rest" && break
        cp "$work/rest" "$work/cur"
        while [ "$(wc -l < "$work/cur")" -gt 1 ] && [ "$runs" -lt "$max_runs" ]; do
            half=$(( $(wc -l < "$work/cur") / 2 ))
            head -n "$half" "$work/cur" > "$work/a"
            tail -n +"$((half + 1))" "$work/cur" > "$work/b"
            if ! cg_ok "$work/a"; then cp "$work/a" "$work/cur"
            elif ! cg_ok "$work/b"; then cp "$work/b" "$work/cur"
            else break; fi   # only a combination of starts crashes; give up
        done
        [ "$(wc -l < "$work/cur")" -eq 1 ] || break
        ./syspart -p $APP -s "$work/cur" -i -a 23 > /dev/null 2>&1
        code=$?
        [ "$code" -ne 0 ] || break
        cat "$work/cur" >> "$work/bad"
        printf '%s\t%s\n' "$(cat "$work/cur")" "$code" >> "$EXCLUDED"
        echo "compute_syscalls: excluding start $(cat "$work/cur") (SysPart exit $code)" >&2
    done
    if [ -s "$EXCLUDED" ] && [ -s "$work/rest" ] && cg_ok "$work/rest"; then
        cp "$work/rest" "$RESOLVED_START"
        ./syspart -p $APP -s $RESOLVED_START -i -a 23 | python3 "$(dirname "$(realpath "$0")")/parse_callgraph_to_json_lowmem.py" - $OUT/callgraph.json
        callgraph_status=("${PIPESTATUS[@]}")
    fi
    rm -rf "$work"
fi
if [ "${callgraph_status[0]}" -ne 0 ]; then
    echo "compute_syscalls: syspart call-graph step (-a 23) exited ${callgraph_status[0]} on $APP; no result" >&2
    exit 3
fi

rm -f "${OUT}/startfuncs_with_addr.txt"
while read -r START_FUNC; do
    start_addr=$(awk -v fname="$START_FUNC" '$1 == fname {print $2}' "$OUT/allfunctions.txt")
    if [ -n "$start_addr" ]; then
        echo "${START_FUNC}_${start_addr}" >> "${OUT}/startfuncs_with_addr.txt"
    fi
done < "$RESOLVED_START"
if [ "$log_flag" = true ]; then
	python3 "$(dirname "$(realpath "$0")")/getsyscalls_lowmem.py" $OUT/callgraph.json $OUT/syscalls_with_callsites.txt $OUT/startfuncs_with_addr.txt --log $OUT/logfile.txt > $OUT/syscalls.txt
else
	python3 "$(dirname "$(realpath "$0")")/getsyscalls_lowmem.py" $OUT/callgraph.json $OUT/syscalls_with_callsites.txt $OUT/startfuncs_with_addr.txt > $OUT/syscalls.txt
fi
