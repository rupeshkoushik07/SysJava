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

# ---- crash exclusion (begin) ----------------------------------------------------
# Some start functions crash SysPart on their own (libsystemd's sd_bus_add_* family).
# Rule: exclude only those and analyse the rest. Each start is tried alone with the
# call-graph step (SYSPART_CRASH_JOBS in parallel, default 6); every one that crashes
# is recorded with its exit code in excluded_starts_syspart_crash.txt. If the rest still
# crashes (only a combination does), bisect for more, up to SYSPART_BISECT_MAX_RUNS
# (default 60) runs. The call graph is then rebuilt from the remaining starts.
# Some starts make SysPart loop instead of crash (Elastic ML controller): each probe is
# limited to SYSPART_PROBE_TIMEOUT seconds (default 900) and a start that runs out is
# excluded the same way, recorded with reason "timeout". The rebuild is limited to
# SYSPART_REBUILD_TIMEOUT seconds (default 3600); running out there fails the library.
# SYSPART_EXCLUDE_CRASHES=0 disables this.
EXCLUDED="${OUT}/excluded_starts_syspart_crash.txt"
rm -f "$EXCLUDED"
if [ "${callgraph_status[0]}" -ne 0 ] && [ "${SYSPART_EXCLUDE_CRASHES:-1}" != 0 ] \
        && [ "$(grep -c . "$RESOLVED_START")" -gt 1 ]; then
    echo "compute_syscalls: call-graph step exited ${callgraph_status[0]}; testing each start function alone" >&2
    work=$(mktemp -d)
    probe_timeout=${SYSPART_PROBE_TIMEOUT:-900}
    # timeout exits 124 (TERM) or 137 (KILL after the grace period) when the limit is hit.
    cg_code() { ( timeout -k 30 "$probe_timeout" ./syspart -p "$APP" -s "$1" -i -a 23 > /dev/null 2>&1 ); echo $?; } 2>/dev/null
    export APP
    grep . "$RESOLVED_START" | xargs -P "${SYSPART_CRASH_JOBS:-6}" -I{} sh -c '
        d=$(mktemp -d -p "$1"); echo "$3" > "$d/s"
        ( timeout -k 30 "$2" ./syspart -p "$APP" -s "$d/s" -i -a 23 > /dev/null 2>&1 ) 2>/dev/null; c=$?
        case "$c" in 124|137) c=timeout ;; esac
        [ "$c" != 0 ] && printf "%s\t%s\n" "$3" "$c" > "$d/bad"; true' _ "$work" "$probe_timeout" {}
    cat "$work"/*/bad 2>/dev/null | sort > "$EXCLUDED"
    cut -f1 "$EXCLUDED" > "$work/bad"
    runs=0
    max_runs=${SYSPART_BISECT_MAX_RUNS:-60}
    while [ "$runs" -lt "$max_runs" ]; do
        grep -vxFf "$work/bad" "$RESOLVED_START" > "$work/rest" || true
        [ -s "$work/rest" ] || break
        runs=$((runs + 1)); [ "$(cg_code "$work/rest")" -eq 0 ] && break
        cp "$work/rest" "$work/cur"
        while [ "$(wc -l < "$work/cur")" -gt 1 ] && [ "$runs" -lt "$max_runs" ]; do
            half=$(( $(wc -l < "$work/cur") / 2 ))
            head -n "$half" "$work/cur" > "$work/a"
            tail -n +"$((half + 1))" "$work/cur" > "$work/b"
            runs=$((runs + 1))
            if [ "$(cg_code "$work/a")" -ne 0 ]; then cp "$work/a" "$work/cur"
            else runs=$((runs + 1)); [ "$(cg_code "$work/b")" -ne 0 ] && cp "$work/b" "$work/cur" || break; fi
        done
        # Crashes only together with another start: drop the smallest crashing group found.
        code=$(cg_code "$work/cur")
        [ "$code" -ne 0 ] || break
        case "$code" in 124|137) code=timeout ;; esac
        while read -r s; do printf '%s\t%s\n' "$s" "$code"; done < "$work/cur" >> "$EXCLUDED"
        cat "$work/cur" >> "$work/bad"
    done
    if [ -s "$EXCLUDED" ]; then
        echo "compute_syscalls: excluded $(grep -c . "$EXCLUDED") start function(s) that crash SysPart: $(cut -f1 "$EXCLUDED" | tr '\n' ' ')" >&2
    fi
    if [ -s "$EXCLUDED" ] && [ -s "$work/rest" ]; then
        cp "$work/rest" "$RESOLVED_START"
        timeout -k 30 "${SYSPART_REBUILD_TIMEOUT:-3600}" ./syspart -p $APP -s $RESOLVED_START -i -a 23 | python3 "$(dirname "$(realpath "$0")")/parse_callgraph_to_json_lowmem.py" - $OUT/callgraph.json
        callgraph_status=("${PIPESTATUS[@]}")
    fi
    rm -rf "$work"
fi
# ---- crash exclusion (end) ------------------------------------------------------
if [ "${callgraph_status[0]}" -ne 0 ]; then
    echo "compute_syscalls: syspart call-graph step (-a 23) exited ${callgraph_status[0]} on $APP; no result" >&2
    # Marks the folder as unanalysable (SysPart crash) for merge_all_syscalls.py.
    echo "call-graph step (-a 23) exited ${callgraph_status[0]}" > "$OUT/syspart_failed.txt"
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
