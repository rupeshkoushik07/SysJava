#!/usr/bin/env bash
#
# Native-declaration coverage rows (Native Declarations, SysJava Accounted For,
# JNI Static / Partial / Dynamic, Not Found, SWAT4J Resolved) for one result set.
#
#   analysis/coverage.sh latest   # work/latest/Final_results_latest_versions/*
#   analysis/coverage.sh jdk8     # work/jdk8/Final_results_JDK8/*
#
# Needs full pipeline results (with Dataset/, i.e. produced by reproduce.sh on
# this machine): the audit reads the libraries' symbol tables with nm.
# For every image it
#   1. runs SWAT4J's JNI mapper (swat4j/swat4j_mapping.py, unmodified; only
#      --jdk-lib points at the container's own JDK libraries) on the same
#      native_methods.txt SysJava used -> analysis/coverage_<set>/swat4j/<image>/
#   2. runs the audit (native_mapping_audit/audit_native_mapping.py)
#      -> analysis/coverage_<set>/per_app_summary.csv (+ per_method.csv, samples)
# Then pass per_app_summary.csv to the table:  AUDIT=<csv> ../1_latest_containers/reproduce.sh
set -euo pipefail
ART="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SET="${1:?latest|jdk8}"
case "$SET" in
    latest) R="$ART/work/latest/Final_results_latest_versions" ;;
    jdk8)   R="$ART/work/jdk8/Final_results_JDK8" ;;
    *) echo "unknown set $SET"; exit 1 ;;
esac
OUT="$ART/analysis/coverage_${SET}"
mkdir -p "$OUT/swat4j"

APPS=(); OVR=()
for d in "$R"/*/; do
    t="$(basename "$d")"
    L="$d/Dataset/LIBS_$t"; M="$d/Bytecode_Analysis/outputs_$t/native_methods.txt"
    [ -d "$L" ] && [ -f "$M" ] || { echo "skip $t (no Dataset or native_methods.txt)"; continue; }
    jdk="$(find "$L" -maxdepth 1 -type d -name 'JDK*_LIBS' | head -1)"
    [ -d "$jdk/amd64" ] && jdk="$jdk/amd64"
    echo "== SWAT4J mapper: $t (jdk-lib ${jdk#$L/})"
    mkdir -p "$OUT/swat4j/$t"
    (cd "$ART/swat4j" && python3 swat4j_mapping.py --libs-dir "$L" ${jdk:+--jdk-lib "$jdk"} \
        --methods "$M" --output-dir "$OUT/swat4j/$t") > "$OUT/swat4j/$t/run.log" 2>&1 \
        || echo "   SWAT4J mapper failed on $t (reported as is, see run.log)"
    APPS+=("$t=$d"); OVR+=("$t=$OUT/swat4j/$t")
done
[ ${#APPS[@]} -gt 0 ] || { echo "no complete results under $R"; exit 1; }

python3 "$ART/analysis/native_mapping_audit/audit_native_mapping.py" --out "$OUT" \
    --app "${APPS[@]}" --swat-override "${OVR[@]}"
echo "coverage rows: $OUT/per_app_summary.csv"
