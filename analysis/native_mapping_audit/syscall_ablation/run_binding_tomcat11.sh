#!/usr/bin/env bash
# Tomcat 11.0.18 (JDK 25): no binding (all exported functions) vs SysJava vs SWAT4J mapping.
# Needs out_mech_latest/ from run_mechanism_latest.sh. Output: out_binding_tomcat11/.
set -euo pipefail
cd "$(dirname "$0")"
T=tomcat_11.0.18-jdk25-temurin-noble
F=$HOME/Prototype/Final_results/$T
python3 binding_vs_nobinding.py --app tomcat_11.0.18 --mech out_mech_latest \
  --syspart $F/Binary_Analysis/syscalls_output_$T \
  --ffi $F/Binary_Analysis/jna_ffi_analysis \
  --libs $F/Dataset/LIBS_$T \
  --rest $F/Binary_Analysis/syscalls_BIN_$T/binary_syscalls.txt \
         $F/Binary_Analysis/syscalls_unanalysed_$T/unanalysed_syscalls.txt \
         $HOME/Prototype/Final_results_echotrace/dockerd_containerd_syscall.txt \
  --profile $F/Binary_Analysis/syscalls_output_$T/$T.txt \
  --out out_binding_tomcat11
