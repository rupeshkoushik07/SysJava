#!/usr/bin/env bash
# Tomcat 11.0.22 (JDK 25, debug-symbol graphs): no binding (all / exported functions) vs
# SysJava vs SWAT4J, over the graphs of ~/Tutorial/EchoTrace/ablation/tomcat_11.0.22
# (run_ablation.sh, owned by another session; only read here).
# SWAT4J: Prototype/swat4j_mapping.py, unmodified, on the pipeline's native_methods.txt.
# Output: out_binding_tomcat11_0_22/. Rerun after the ablation finishes more libraries.
set -euo pipefail
cd "$(dirname "$0")"
HERE=$PWD
L=$HOME/Tutorial/EchoTrace_latest
LIBS=$L/Final_results_latest_versions/tomcat_11.0.22/Dataset/LIBS_tomcat_11.0.22
SW=$HERE/swat4j_latest/tomcat_11.0.22
if [ ! -f "$SW/swat4j_mapped_methods.txt" ]; then
  mkdir -p "$SW"
  (cd "$HOME/Prototype" && python3 swat4j_mapping.py --libs-dir "$LIBS" --jdk-lib "$LIBS/JDK25_LIBS" \
     --methods "$L/workspaces/tomcat_11.0.22/outputs_tomcat_11.0.22/native_methods.txt" \
     --output-dir "$SW") > "$SW/run.log" 2>&1
fi
python3 binding_arms_lean.py --ablation "$HOME/Tutorial/EchoTrace/ablation/tomcat_11.0.22" \
  --swat "$SW/swat4j_mapped_methods.txt" --out out_binding_tomcat11_0_22
