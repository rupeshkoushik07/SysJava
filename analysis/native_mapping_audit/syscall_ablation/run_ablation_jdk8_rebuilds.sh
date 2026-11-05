#!/usr/bin/env bash
# Entry-point ablation for the JDK 8 rebuilds (Debian 10 + Temurin 8) in
# Final_results_JDK8/<app>-jdk8-buster. Their datasets are symbolized from the start,
# so SysPart's graphs are in Binary_Analysis/ (not Binary_Analysis_symbolized/).
#
# SWAT4J's mapping (Prototype/swat4j_mapping.py, unmodified) has never been run on these
# images; it is run here on each image's own native_methods.txt. The host JDK 8 that
# earlier reruns scanned is no longer installed, so --jdk-lib points at the container's
# JDK8_LIBS (environment-only change, as for OrientDB).
#
# Usage: run_ablation_jdk8_rebuilds.sh <app>-jdk8-buster [...]
set -euo pipefail
cd "$(dirname "$0")"
R=${JDK8_RESULTS:-$HOME/Tutorial/EchoTrace/Final_results_JDK8}
P=${PROTOTYPE:-$HOME/Prototype}
HERE=$PWD

audit_apps=() overrides=() graph_apps=()
for app in "$@"; do
  d=$R/$app
  L=$d/Dataset/LIBS_$app
  sw=$HERE/swat4j_jdk8/$app
  if [ ! -f "$sw/swat4j_mapped_methods.txt" ]; then
    mkdir -p "$sw"
    (cd "$P" && python3 swat4j_mapping.py --libs-dir "$L" --jdk-lib "$L/JDK8_LIBS/amd64" \
        --methods "$d/Bytecode_Analysis/outputs_$app/native_methods.txt" --output-dir "$sw") \
        > "$sw/run.log" 2>&1
  fi
  audit_apps+=("$app=$d")
  overrides+=("$app=$sw")
  graph_apps+=("$app=$d/Binary_Analysis/syscalls_output_$app")
done

(cd .. && python3 audit_native_mapping.py --out out_jdk8 --app "${audit_apps[@]}" --swat-override "${overrides[@]}")
python3 entrypoint_ablation.py --mapping ../out_jdk8/per_method.csv --out out_jdk8 --app "${graph_apps[@]}"
