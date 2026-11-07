#!/bin/bash
# Ablation: analysis scoping vs. binding recovery.
#
# For every library SysJava analysed with recovered bindings, run SysPart twice
# on the same archived inputs, changing only the start functions:
#   A  every function SysPart identifies in the library (exported or not)
#   B  the bound functions the original run resolved (startfuncs_with_addr.txt)
#   M  every library function the app's native methods are mapped to in
#      mapped_method_syscalls.txt, whether or not the original run rooted it
#   ALL  SysPart's all-functions mode (-a 28): every function of the library
#        AND of every dependency loaded with it (libc, libjvm, ...); upper bound
#
# Both variants use the same SysPart build and the same steps as
# compute_syscalls.sh, except that start names resolve only to addresses in the
# analysed library itself (compute_syscalls.sh matches names in any module).
#
# Usage: ./run_ablation.sh <img> [parallel-jobs]
#   RESULTS=<archived Final_results/<img> dir>  (default: ~/Prototype/...)
#   ONLY=<library name>                          run a single library
#   SKIP="<lib> <lib>"                           libraries to leave out
#   VARIANTS="A B ALL"                           variants to run (default; M on request)
#   LEAN=1     compute syscalls with lean_syscalls.py instead of the JSON
#              step (same result; needed for libjvm A, whose JSON exceeds RAM)
#   LOADED=<file>  one library path per line, analysed from every function as
#              variant U (e.g. loaded libraries SysJava mapped nothing to);
#              run with VARIANTS=U to skip the mapped libraries
#   SYMBOLIZED=1   analyse the libraries and resolve their dependencies from
#              Dataset_symbolized/ (symbolize_dataset.py), so stripped
#              dependencies such as libcrypto do not appear as fuzzyfunc-0x...
#   TARGETS=<tsv>  "lib<TAB>library path<TAB>binding start list" per line, for
#              runs with no archived Binary_Analysis (e.g. FFM downcall symbols).
#              Each arm gets its own call graph, rooted at its own start set,
#              kept as <arm>/<lib>/callgraph_a23.txt.zst. One graph rooted at
#              every function does NOT serve for B: SysPart resolves indirect
#              calls against functions whose address is taken in reachable code,
#              so the larger graph adds indirect targets a binding-only run never
#              has (Tomcat 11 libssl: 59 syscalls over the all-roots graph, 44
#              from its own graph, the same as the pipeline's 44).
#   OUT_DIR=<dir>  output folder (default ./<img>)
#   ARMS="A B"  arms to run for TARGETS (e.g. ARMS=B to add the binding arm to
#              a library whose A is done; its listings in A/<lib> are reused)
#   NICE=10  JOB_MEM_GB=12  JOB_TIMEOUT=7200   niceness, virtual-memory cap and
#              time limit per SysPart run (shared host)
set -euo pipefail

IMG="${1:?usage: run_ablation.sh <img> [parallel-jobs]}"
JOBS="${2:-4}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYSPART_APP="${SYSPART_APP:-$(cd "$HERE/../SysPartCode/analysis/app" && pwd)}"
RESULTS="${RESULTS:-$HOME/Prototype/Final_results_echotrace/$IMG}"
B_OUT="$RESULTS/Binary_Analysis/syscalls_output_$IMG"
ARCH_LIBS="$RESULTS/Dataset/LIBS_$IMG"
LIBS_DIR="$ARCH_LIBS"
[ "${SYMBOLIZED:-0}" = 1 ] && LIBS_DIR="$RESULTS/Dataset_symbolized/LIBS_$IMG"
MAPPING="$RESULTS/Bytecode_Analysis/outputs_$IMG/mapped_method_syscalls.txt"
OUT="${OUT_DIR:-$HERE/$IMG}"   # OUT_DIR: write into another folder (e.g. a rerun next to the original)

[ -x "$SYSPART_APP/syspart" ] || { echo "syspart not built in $SYSPART_APP" >&2; exit 1; }
[ -n "${TARGETS:-}" ] || [ -d "$B_OUT" ] || { echo "no archived binding run at $B_OUT" >&2; exit 1; }

mkdir -p "$OUT/starts/A" "$OUT/starts/B" "$OUT/starts/M"
JOBLIST="$OUT/jobs.txt"
: > "$JOBLIST"

for d in "$B_OUT"/*/; do
    [ -z "${TARGETS:-}" ] || break     # TARGETS lists exactly what to run
    lib="$(basename "$d")"
    [ -f "$d/allfunctions.txt" ] || continue
    [ -z "${ONLY:-}" ] || [ "$lib" = "$ONLY" ] || continue
    case " ${SKIP:-} " in *" $lib "*) continue ;; esac

    # Exact file the original run analysed, taken from its own module records.
    libpath="$(awk -v lib="$lib" '{m=$3; sub(/^module-/,"",m); n=split(m,p,"/");
                if (p[n]==lib) {print m; exit}}' "$d/allfunctions.txt")"
    if [ -z "$libpath" ] || [ ! -f "$libpath" ]; then
        echo "skip $lib: analysed file not found ($libpath)" >&2
        continue
    fi
    # Same file from the symbolized dataset, when that is in use.
    case "$libpath" in "$ARCH_LIBS"/*)
        [ ! -f "$LIBS_DIR/${libpath#"$ARCH_LIBS"/}" ] || libpath="$LIBS_DIR/${libpath#"$ARCH_LIBS"/}" ;;
    esac

    # A: every function SysPart lists in this library's own module.
    awk -v lib="$lib" '{m=$3; sub(/^module-/,"",m); n=split(m,p,"/");
         if (p[n]==lib) print $1}' "$d/allfunctions.txt" | sort -u > "$OUT/starts/A/$lib.txt"
    # B: the bound start functions the original run resolved (name_addr -> name).
    sed -E 's/_[0-9a-f]+$//' "$d/startfuncs_with_addr.txt" | sort -u > "$OUT/starts/B/$lib.txt"
    # M: lines "LIBS_<img>/.../<lib>:<java method> -> <symbol> [TAG]"; a "?" in
    # the tag marks a symbol the mapper could not confirm in the library.
    if [ -f "$MAPPING" ]; then
        awk -v lib="$lib" '{split($0, a, " -> "); split(a[1], b, ":"); n=split(b[1], p, "/");
             if (b[1] ~ /^LIBS_/ && p[n]==lib && a[2] !~ /\?/) {split(a[2], c, " "); print c[1]}}' \
            "$MAPPING" | sort -u > "$OUT/starts/M/$lib.txt"
    fi

    for v in ${VARIANTS:-A B ALL}; do
        [ "$v" = U ] && continue
        echo "$v $lib $libpath" >> "$JOBLIST"
    done
done

if [ -n "${LOADED:-}" ]; then
    mkdir -p "$OUT/starts/U"
    while IFS= read -r libpath; do
        [ -n "$libpath" ] || continue
        lib="$(basename "$libpath")"
        [ -z "${ONLY:-}" ] || [ "$lib" = "$ONLY" ] || continue
        [ -f "$libpath" ] || { echo "skip $libpath: not found" >&2; continue; }
        rm -f "$OUT/starts/U/$lib.txt"    # derived by run_one from the listing
        echo "U $lib $libpath" >> "$JOBLIST"
    done < "$LOADED"
fi

if [ -n "${TARGETS:-}" ]; then
    while IFS=$'\t' read -r lib libpath bind; do
        [ -n "$lib" ] || continue
        [ -z "${ONLY:-}" ] || [ "$lib" = "$ONLY" ] || continue
        case " ${SKIP:-} " in *" $lib "*) continue ;; esac
        if [ ! -f "$libpath" ] || [ ! -f "$bind" ]; then
            echo "skip $lib: $libpath or $bind not found" >&2
            continue
        fi
        sort -u "$bind" > "$OUT/starts/B/$lib.txt"
        rm -f "$OUT/starts/A/$lib.txt"   # derived by run_one from the listing
        echo "G $lib $libpath" >> "$JOBLIST"
    done < "$TARGETS"
fi

USER_LIBRARY_PATH="$LIBS_DIR"
while IFS= read -r sub; do
    USER_LIBRARY_PATH="$USER_LIBRARY_PATH:$sub"
done < <(find "$LIBS_DIR" -type d | sort)
export USER_LIBRARY_PATH SYSPART_APP OUT HERE
export JOB_MEM_GB="${JOB_MEM_GB:-}" JOB_TIMEOUT="${JOB_TIMEOUT:-}" ARMS="${ARMS:-A B}"

# Variant G: for each arm in $ARMS, a call graph rooted at that arm's start set
# and the syscalls reachable over it. The function listing (-a 25) and syscall
# sites (-a 24) do not depend on the start set and are shared.
run_graph() {
    local lib="$1" libpath="$2" adir="$OUT/A/$1" bdir="$OUT/B/$1"
    local first t0 limit=() arms="${ARMS:-A B}" status v
    mkdir -p "$adir" "$bdir"
    t0=$(date +%s)
    [ -z "$JOB_TIMEOUT" ] || limit=(timeout "$JOB_TIMEOUT")
    first="$(nm -D --defined-only "$libpath" 2>/dev/null \
        | awk '$2 ~ /^[TWi]$/ {sub(/@.*/, "", $3); print $3; exit}')"
    # Not an `if` condition, so errexit holds inside: any failed step (timeout,
    # memory cap) fails the subshell instead of leaving a partial result.
    (
        set -eo pipefail
        [ -z "$JOB_MEM_GB" ] || ulimit -v $(( JOB_MEM_GB * 1048576 ))
        cd "$SYSPART_APP"
        # A fresh A run lists again; a B-only run reuses A's listings.
        if [[ " $arms " == *" A "* ]] || [ ! -s "$adir/allfunctions.txt" ] \
                || [ ! -s "$adir/syscalls_with_callsites.txt" ]; then
            "${limit[@]}" ./syspart -p "$libpath" -s "$first" -a 25 > "$adir/allfunctions.txt"
            "${limit[@]}" ./syspart -p "$libpath" -s "$first" -a 24 > "$adir/syscalls_with_callsites.txt"
        fi
        awk -v lib="$lib" '{m=$3; sub(/^module-/,"",m); n=split(m,p,"/");
             if (p[n]==lib) print $1}' "$adir/allfunctions.txt" | sort -u > "$OUT/starts/A/$lib.txt"
        cp "$adir/allfunctions.txt" "$adir/syscalls_with_callsites.txt" "$bdir/"
        for v in $arms; do
            local d="$OUT/$v/$lib"
            awk -v lib="$lib" 'NR==FNR {want[$1]=1; next}
                 {m=$3; sub(/^module-/,"",m); n=split(m,p,"/");
                  if (p[n]==lib && ($1 in want)) print $1"_"$2}' \
                "$OUT/starts/$v/$lib.txt" "$adir/allfunctions.txt" > "$d/startfuncs_with_addr.txt"
            "${limit[@]}" ./syspart -p "$libpath" -s "$OUT/starts/$v/$lib.txt" -i -a 23 \
                | zstd -q -T1 -f -o "$d/callgraph_a23.txt.zst"
            zstdcat "$d/callgraph_a23.txt.zst" \
                | python3 "$HERE/lean_syscalls.py" - "$d/syscalls_with_callsites.txt" \
                    "$d/startfuncs_with_addr.txt" | sort -u > "$d/syscalls.txt"
        done
    ) > "$OUT/${arms// /}_$lib.log" 2>&1
    status=$?
    if [ $status -eq 0 ]; then
        echo "G $lib $(for v in $arms; do printf '%s: starts=%s syscalls=%s  ' "$v" \
            "$(wc -l < "$OUT/$v/$lib/startfuncs_with_addr.txt")" "$(wc -l < "$OUT/$v/$lib/syscalls.txt")"; done)secs=$(( $(date +%s) - t0 ))"
    else
        for v in $arms; do rm -f "$OUT/$v/$lib/syscalls.txt"; done
        echo "G $lib FAILED ($arms) after $(( $(date +%s) - t0 )) s; see $OUT/${arms// /}_$lib.log"
    fi
}
export -f run_graph

run_one() {
    local v="$1" lib="$2" libpath="$3"
    local starts="$OUT/starts/$v/$lib.txt" dir="$OUT/$v/$lib"
    local first t0
    [ "$v" != G ] || { run_graph "$lib" "$libpath"; return; }
    mkdir -p "$dir"
    t0=$(date +%s)
    if [ "$v" = ALL ]; then
        ( cd "$SYSPART_APP" && ./syspart -p "$libpath" -s all -i -a 28 ) \
            2> "$dir/run.log" | sort -u > "$dir/syscalls.txt"
        echo "$v $lib syscalls=$(wc -l < "$dir/syscalls.txt") secs=$(( $(date +%s) - t0 ))"
        return
    fi
    first="$(head -1 "$starts" 2>/dev/null || true)"
    # Variant U has no start list yet: any exported function serves for the
    # listing steps, and the list is every function of the library they print.
    [ -n "$first" ] || first="$(nm -D --defined-only "$libpath" 2>/dev/null \
        | awk '$2 ~ /^[TWi]$/ {sub(/@.*/, "", $3); print $3; exit}')"
    (
        cd "$SYSPART_APP"
        ./syspart -p "$libpath" -s "$first" -a 25 > "$dir/allfunctions.txt"
        if [ ! -s "$starts" ]; then
            awk -v lib="$lib" '{m=$3; sub(/^module-/,"",m); n=split(m,p,"/");
                 if (p[n]==lib) print $1}' "$dir/allfunctions.txt" | sort -u > "$starts"
        fi
        ./syspart -p "$libpath" -s "$first" -a 24 > "$dir/syscalls_with_callsites.txt"
        awk -v lib="$lib" 'NR==FNR {want[$1]=1; next}
             {m=$3; sub(/^module-/,"",m); n=split(m,p,"/");
              if (p[n]==lib && ($1 in want)) print $1"_"$2}' \
            "$starts" "$dir/allfunctions.txt" > "$dir/startfuncs_with_addr.txt"
        if [ "${LEAN:-0}" = 1 ]; then
            ./syspart -p "$libpath" -s "$starts" -i -a 23 \
                | python3 "$HERE/lean_syscalls.py" - "$dir/syscalls_with_callsites.txt" \
                    "$dir/startfuncs_with_addr.txt" | sort -u > "$dir/syscalls.txt"
        else
            ./syspart -p "$libpath" -s "$starts" -i -a 23 \
                | python3 src/scripts/parse_callgraph_to_json.py - "$dir/callgraph.json"
            python3 src/scripts/getsyscalls.py "$dir/callgraph.json" \
                "$dir/syscalls_with_callsites.txt" "$dir/startfuncs_with_addr.txt" \
                | sort -u > "$dir/syscalls.txt"
        fi
    ) > "$dir/run.log" 2>&1
    echo "$v $lib starts=$(wc -l < "$starts") resolved=$(wc -l < "$dir/startfuncs_with_addr.txt") syscalls=$(wc -l < "$dir/syscalls.txt") secs=$(( $(date +%s) - t0 ))"
}
export -f run_one

echo "image: $IMG   inputs: $RESULTS   jobs: $(wc -l < "$JOBLIST")"
nice -n "${NICE:-0}" xargs -P "$JOBS" -L 1 bash -c 'run_one "$@"' _ < "$JOBLIST"
