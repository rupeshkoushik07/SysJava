#!/usr/bin/env bash
#
# Re-run SysPart over the symbolized dataset of analysed targets.
#
# symbolize_dataset.py restores .symtab into Final_results_echotrace/<target>/
# Dataset_symbolized/. This script repeats every analysis recorded under
# <target>/Binary_Analysis/ -- same ELF, same start functions -- against that
# copy, so call graphs carry real function names instead of fuzzyfunc-0x...
# Results go to <target>/Binary_Analysis_symbolized/ with the same layout; the
# original Binary_Analysis/ is left untouched for comparison.
#
# Before running, the SONAME links that extraction drops are recreated in the
# symbolized LIBS copy (relink_sonames.sh). Without them SysPart cannot find
# e.g. libc.so.6 in the mirror and silently falls back to the host's libc.
#
# Usage:
#   ./scripts/rerun_syspart_symbolized.sh                  # every target
#   ./scripts/rerun_syspart_symbolized.sh storm_2.4.0 ...  # a subset
#
# Optional:
#   JOBS=3             parallel SysPart runs (default 3)
#   JOB_TIMEOUT=7200   seconds per ELF before it is abandoned (default 7200)
#   JOB_MEM_GB=18      virtual-memory cap per run; libjvm graphs can need >30GB
#   ONLY=libjava.so    restrict to result directories with this name
#   RESUME=1           skip ELFs whose rerun already produced syscalls.txt
#   EXCLUDE="t/elf"    space-separated target/elf pairs to skip
#   START_MODE=exports start each library from all its exported functions
#                      instead of the JNI mapping (writes Binary_Analysis_exports/)
#   SYSPART_APP=dir    SysPart build to use (default: pinned, see syspart-pin/PINNED.md)
#   PHASE=light|heavy  light skips the HEAVY_RE ELFs, heavy runs only them
#                      (default: all). On a 62 GB host run light with JOBS=4
#                      JOB_MEM_GB=12, then heavy with JOBS=1 JOB_MEM_GB=55.
#   RESULTS_ROOT=dir   results tree to use (default: Final_results_echotrace/)
#   JOB_STACK_MB=1024  stack limit per run (Egalito recursion on a full libjvm)
#   HEAVY_RE           ELF names whose call graphs need 30-40 GB; anything that
#                      links libjvm.so is treated as heavy as well
#                      (default: libjvm.so and libawt*)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RESULTS_ROOT="${RESULTS_ROOT:-${PROJECT_ROOT}/Final_results_echotrace}"
# SYSPART_APP selects the SysPart build (its analysis/app directory). The
# default is the pinned build documented in syspart-pin/PINNED.md.
SYSPART_APP="${SYSPART_APP:-/home/user/SysPartCode/analysis/app}"
JOBS="${JOBS:-3}"
JOB_TIMEOUT="${JOB_TIMEOUT:-7200}"
JOB_MEM_GB="${JOB_MEM_GB:-18}"
JOB_STACK_MB="${JOB_STACK_MB:-1024}"
PHASE="${PHASE:-all}"
START_MODE="${START_MODE:-mapped}"
OUT_NAME="${OUT_NAME:-$([ "$START_MODE" = exports ] && echo Binary_Analysis_exports || echo Binary_Analysis_symbolized)}"
HEAVY_RE="${HEAVY_RE:-^(libjvm\.so|libawt.*\.so)$}"

if [ ! -x "${SYSPART_APP}/syspart" ]; then
    echo "ERROR: syspart not built at ${SYSPART_APP}/syspart" >&2
    exit 1
fi

if [ "$#" -gt 0 ]; then
    TARGETS=("$@")
else
    mapfile -t TARGETS < <(find "$RESULTS_ROOT" -mindepth 2 -maxdepth 2 -type d -name Dataset_symbolized \
        -printf '%h\n' | xargs -n1 basename | sort)
fi

# Same lookup rule as analyse_lib.sh: exact filename first, then a versioned
# match, then the <lib>_<jar>.so name extraction gives JAR-bundled libraries;
# shortest path wins; regular x86-64 files only. JAR bundles ship a build per
# platform, so a same-named 32-bit copy (cassandra's libjnidispatch.so) can
# shadow the real one, and Egalito rejects it outright.
find_artifact() {
    local name="$1"; shift
    local root
    for root in "$@"; do
        [ -d "$root" ] || continue
        for pattern in "$name" "${name}.*" "${name%.so}_*.so"; do
            find "$root" -type f -name "$pattern" -not -name '*.stripped' 2>/dev/null \
                | awk '{print length"\t"$0}' | sort -n | cut -f2-
        done
    done | while IFS= read -r candidate; do
        readelf -h "$candidate" 2>/dev/null | grep -q 'X86-64' && echo "$candidate"
    done | head -1 || true
}

# Name of the function at the ELF entry point, now that symbols are restored:
# _start for C programs, _rt0_amd64_linux for Go (gosu), and so on.
entry_symbol() {
    local entry sym
    entry=$(readelf -h "$1" 2>/dev/null | awk '/Entry point/{print $4}')
    sym=$(nm "$1" 2>/dev/null | awk -v e="${entry#0x}" '
        { a = $1; sub(/^0+/, "", a); b = e; sub(/^0+/, "", b) }
        a == b && $2 ~ /[Tt]/ && !found { print $3; found = 1 }') || true
    echo "${sym:-_start}"
}

# Emit one tab-separated job per original result directory:
#   artifact  start-file  output-dir  library-path  log-label
plan_jobs() {
    local target="$1"
    local sym="${RESULTS_ROOT}/${target}/Dataset_symbolized"
    local libs="${sym}/LIBS_${target}" bins="${sym}/BINARIES_${target}"
    local starts="${RESULTS_ROOT}/${target}/Bytecode_Analysis"
    local out_root="${RESULTS_ROOT}/${target}/${OUT_NAME}"
    local generated="${out_root}/.start_files"
    mkdir -p "$generated"

    local lib_path="$libs" d
    while IFS= read -r d; do lib_path="${lib_path}:${d}"; done < <(find "$libs" -mindepth 1 -type d | sort)

    local dir kind name artifact start
    for dir in "${RESULTS_ROOT}/${target}"/Binary_Analysis/*/*/; do
        dir="${dir%/}"
        kind="$(basename "$(dirname "$dir")")"
        name="$(basename "$dir")"
        [ -n "${ONLY:-}" ] && [ "$name" != "$ONLY" ] && continue
        # EXCLUDE="target/elf ..." skips ELFs SysPart cannot complete (Go binaries,
        # elasticsearch's controller) so RESUME does not retry them forever.
        case " ${EXCLUDE:-} " in *" ${target}/${name} "*) continue ;; esac
        # Binaries start from their entry point in both modes; exports mode
        # only re-analyses libraries.
        [ "$START_MODE" = exports ] && [[ "$kind" == syscalls_BIN_* ]] && continue

        if [[ "$kind" == syscalls_BIN_* ]]; then
            artifact="$(find_artifact "$name" "$bins" "$libs")"
        else
            artifact="$(find_artifact "$name" "$libs" "$bins")"
        fi
        if [ -z "$artifact" ]; then
            echo "SKIP ${target}/${name}: not in Dataset_symbolized" >&2
            continue
        fi

        # Anything linked against libjvm.so pulls the whole JVM into its call
        # graph (35-46k functions) and needs far more than a light job's cap.
        if [[ "$name" =~ $HEAVY_RE ]] || readelf -d "$artifact" 2>/dev/null | grep -c '\[libjvm\.so\]' >/dev/null; then
            [ "$PHASE" = light ] && continue
        else
            [ "$PHASE" = heavy ] && continue
        fi

        # Start functions: the binary's start.txt, else the mapper's file for
        # the library, else the names the original run resolved, else _start.
        # START_MODE=exports replaces the JNI-mapped starts of a library with
        # every function it exports (no Java binding information).
        start=""
        if [ "$START_MODE" = exports ] && [[ "$kind" != syscalls_BIN_* ]]; then
            start="${generated}/${kind}__${name}.exports.txt"
            nm -D --defined-only "$artifact" 2>/dev/null | awk '$2 ~ /^[TtWi]$/ {print $3}' \
                | sed 's/@.*//' | sort -u > "$start"
            [ -s "$start" ] || entry_symbol "$artifact" > "$start"
        elif [ -s "${dir}/start.txt" ]; then
            start="${dir}/start.txt"
        else
            start="$(find "$starts" -path '*jna_detector_work*' -prune -o -type f -name "${name}.txt" -print 2>/dev/null | head -1 || true)"
        fi
        if [ -z "$start" ]; then
            start="${generated}/${kind}__${name}.txt"
            if [ -s "${dir}/startfuncs_with_addr.txt" ]; then
                sed 's/_[0-9a-f]*$//' "${dir}/startfuncs_with_addr.txt" > "$start"
            else
                entry_symbol "$artifact" > "$start"
            fi
        fi

        if [ "${RESUME:-0}" = 1 ] && [ -s "${out_root}/${kind}/${name}/syscalls.txt" ]; then
            continue
        fi
        printf '%s\t%s\t%s\t%s\t%s\n' "$artifact" "$start" "${out_root}/${kind}/${name}" "$lib_path" "${target}/${name}"
    done
}

run_job() {
    local artifact="$1" start="$2" out="$3" lib_path="$4" label="$5"
    rm -rf "$out"
    mkdir -p "$out"
    local began=$SECONDS status=0
    (
        cd "$SYSPART_APP"
        ulimit -v $((JOB_MEM_GB * 1024 * 1024))
        # Egalito's slicing recurses deeply on a full libjvm and overflows the
        # default 8 MB stack; unlimited lets a runaway recursion eat the host.
        ulimit -s $((JOB_STACK_MB * 1024))
        USER_LIBRARY_PATH="$lib_path" timeout "$JOB_TIMEOUT" \
            "${SCRIPT_DIR}/compute_syscalls_lowmem.sh" "$artifact" "$out" "$start" --log
    ) > "${out}/syspart_run.log" 2>&1 || status=$?
    cp "$start" "${out}/start.txt" 2>/dev/null || true
    # Record which SysPart build produced this result.
    echo "$(realpath "${SYSPART_APP}/syspart") $(md5sum < "${SYSPART_APP}/syspart" | cut -c1-12)" \
        > "${out}/syspart_build.txt"
    # compute_syscalls.sh exits 0 even when syspart died mid-graph (bad_alloc,
    # segfault); an empty callgraph.json is a failure, not "no syscalls".
    if [ "$status" = 0 ] && ! grep -q '"id"' "${out}/callgraph.json" 2>/dev/null; then
        status="empty-callgraph"
        rm -f "${out}/syscalls.txt"
    fi
    local funcs=0 fuzzy=0 sys=0
    [ -f "${out}/allfunctions.txt" ] && funcs=$(wc -l < "${out}/allfunctions.txt") \
        && fuzzy=$(grep -c '^fuzzyfunc' "${out}/allfunctions.txt" || true)
    [ -f "${out}/syscalls.txt" ] && sys=$(wc -l < "${out}/syscalls.txt")
    printf '%s\texit=%s\tfunctions=%s\tfuzzy=%s\tsyscalls=%s\t%ss\n' \
        "$label" "$status" "$funcs" "$fuzzy" "$sys" $((SECONDS - began))
}
export -f run_job
export SYSPART_APP SCRIPT_DIR JOB_TIMEOUT JOB_MEM_GB JOB_STACK_MB

for target in "${TARGETS[@]}"; do
    libs="${RESULTS_ROOT}/${target}/Dataset_symbolized/LIBS_${target}"
    if [ ! -d "$libs" ]; then
        echo "SKIP ${target}: run scripts/symbolize_dataset.py ${target} first" >&2
        continue
    fi
    bash "${SCRIPT_DIR}/relink_sonames.sh" "$libs" > /dev/null
done

for target in "${TARGETS[@]}"; do
    [ -d "${RESULTS_ROOT}/${target}/Dataset_symbolized" ] && plan_jobs "$target"
done | xargs -P "$JOBS" -d '\n' -I{} bash -c 'IFS=$'"'"'\t'"'"' read -r a s o l n <<< "$1"; run_job "$a" "$s" "$o" "$l" "$n"' _ {}
