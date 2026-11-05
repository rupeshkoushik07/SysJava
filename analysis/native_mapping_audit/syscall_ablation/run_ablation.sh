#!/usr/bin/env bash
# Entry-point ablation on the debug-symbol SysPart call graphs.
# Needs ../out/per_method.csv (../run_audit.sh) for the five audit apps; Cassandra 5
# gets its own mapping audit into ../out_c5.
set -euo pipefail
cd "$(dirname "$0")"
R=${JDK8_RESULTS:-$HOME/Tutorial/EchoTrace/Final_results_JDK8}
P=${PROTOTYPE:-$HOME/Prototype}
graphs() { echo "$1=$R/$1/Binary_Analysis_symbolized/syscalls_output_$1"; }

python3 entrypoint_ablation.py --out out \
  --app $(graphs zookeeper_3.4.14) $(graphs tomcat_7.0) $(graphs cassandra_3.0.29) \
        $(graphs orientdb_3.2.19) $(graphs jruby_9.4.2.0)

C5=cassandra_5.0.6-bookworm
(cd .. && python3 audit_native_mapping.py --out out_c5 --app $C5=$P/Final_results_echotrace/$C5)
python3 entrypoint_ablation.py --mapping ../out_c5/per_method.csv --out out_c5 --app $(graphs $C5)
