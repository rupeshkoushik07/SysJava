#!/usr/bin/env bash
# Per-library, per-mechanism ablation on the newer containers (JDK 12-25), where JNA and
# Panama FFM bindings occur. Graphs: ~/Prototype/Final_results/<app>; SWAT4J mapping
# (unmodified swat4j_mapping.py) in swat4j_latest/<app>; audits ../out_latest, ../out_tomcat11.
# jetty_latest is left out: its libjvm callgraph.json is truncated (17,302 of 52,878
# functions), so neither arm's reachability is meaningful.
set -euo pipefail
cd "$(dirname "$0")"
F=$HOME/Prototype/Final_results
g() { echo "$1=$F/$2/Binary_Analysis/syscalls_output_$2"; }
python3 mechanism_ablation.py --out out_mech_latest \
  --mapping ../out_latest/per_method.csv ../out_tomcat11/per_method.csv \
  --app $(g tomcat_11.0.18 tomcat_11.0.18-jdk25-temurin-noble) \
        $(g elasticsearch_7.1.0 elasticsearch_7.1.0) \
        $(g solr_slim solr_slim) \
        $(g groovy_latest groovy_latest) \
        $(g zookeeper_latest zookeeper_latest) \
  --ffi tomcat_11.0.18=$F/tomcat_11.0.18-jdk25-temurin-noble/Binary_Analysis/jna_ffi_analysis \
        elasticsearch_7.1.0=$F/elasticsearch_7.1.0/Binary_Analysis/jna_ffi_analysis
