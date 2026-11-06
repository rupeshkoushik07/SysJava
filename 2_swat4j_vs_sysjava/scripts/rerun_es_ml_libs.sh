#!/usr/bin/env bash
# Rerun the stage-8 SysPart analysis of Elasticsearch's ML libraries that were
# skipped (user decision 2026-11-06), the same way analyze_unanalysed_loaded_libs.py
# runs it: compute_syscalls.sh from the library's exported functions, crash
# exclusion with SYSPART_CRASH_JOBS probes and the per-probe timeout. Then
# stages 9-10 again. Previous skip notes move to <lib>/_skipped_attempt/.
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
T=elasticsearch_7.5.2-jdk8-buster
WS="${REPO}/jdk8_workspaces/${T}"
BA="${WS}/Final_results/${T}/Binary_Analysis"
SLIBS="${REPO}/Final_results_JDK8/${T}/Dataset_symbolized/LIBS_${T}"
ULP="$SLIBS"
for d in "$SLIBS"/JDK*_LIBS; do [ -d "$d" ] && ULP="$ULP:$d:$(find "$d" -mindepth 1 -type d | sort | paste -sd:)"; done
export SYSPART_CRASH_JOBS="${SYSPART_CRASH_JOBS:-12}"
for lib in libMlCore.so libboost_log-gcc7-mt-x64-1_71.so.1.71.0 libboost_log_setup-gcc7-mt-x64-1_71.so.1.71.0; do
    out="${BA}/syscalls_unanalysed_${T}/${lib}"; start="${BA}/startfuncs_unanalysed_${T}/${lib}.txt"
    [ -f "$start" ] && [ -f "${SLIBS}/${lib}" ] || { echo "missing start file or library for $lib"; continue; }
    until [ "$(free -g | awk '/^Mem:/{print $7}')" -ge 30 ]; do sleep 60; done
    mkdir -p "${out}/_skipped_attempt"
    find "$out" -maxdepth 1 -type f -exec mv {} "${out}/_skipped_attempt/" \;
    echo "$(date +%T) START $lib starts=$(grep -c . "$start") jobs=${SYSPART_CRASH_JOBS}"
    s=$(date +%s)
    (cd "${WS}/SysPartCode/analysis/app" && USER_LIBRARY_PATH="$ULP" \
        src/scripts/compute_syscalls.sh "${SLIBS}/${lib}" "$out" "$start" --log > "${out}/logfile.txt" 2>&1)
    rc=$?
    echo "$(date +%T) DONE $lib exit=$rc $(( ($(date +%s) - s) / 60 ))min syscalls=$(grep -c . "${out}/syscalls.txt" 2>/dev/null || echo none) excluded=$(grep -c . "${out}/excluded_starts_syspart_crash.txt" 2>/dev/null || echo 0) timeouts=$(grep -c timeout "${out}/excluded_starts_syspart_crash.txt" 2>/dev/null || echo 0)"
done
echo "$(date +%T) stages 9-10"
bash "${REPO}/scripts/run_jdk8_target.sh" "$T" 9 > /dev/null 2>&1
echo "$(date +%T) $(grep -E '^RESULT=' "${REPO}/Final_results_JDK8/${T}/pipeline_run.log" | tail -1)"
