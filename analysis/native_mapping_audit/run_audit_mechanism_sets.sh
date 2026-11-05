#!/usr/bin/env bash
# Mapping audits for the per-library / per-mechanism comparison (MAPPING_PER_LIBRARY.md)
# that run_audit.sh and syscall_ablation/run_ablation*.sh do not already produce:
#
#   out_jdk8_gs   Groovy 4.0.0 + Solr 8.7.0, JDK 8 debug-symbol rebuilds
#   out_tomcat11  Tomcat 11.0.18, JDK 25 (Panama FFM into libssl/libcrypto)
#   out_latest    Elasticsearch 7.1.0 (JDK 12, JNA), Jetty/Solr latest (JDK 25),
#                 Groovy latest (JDK 21), ZooKeeper latest (JDK 17)
#
# SWAT4J's mapping is Prototype/swat4j_mapping.py, unmodified. Only --jdk-lib is set, to
# each container's own JDK libraries (the host JDK 8 it defaults to is no longer
# installed). Its output goes to syscall_ablation/swat4j_{jdk8,latest}/<app>/ and is
# reused if present.
set -euo pipefail
cd "$(dirname "$0")"
HERE=$PWD
P=${PROTOTYPE:-$HOME/Prototype}
F=$P/Final_results
R=${JDK8_RESULTS:-$HOME/Tutorial/EchoTrace/Final_results_JDK8}

# swat <out_dir> <libs_dir> <jdk_lib_dir> <native_methods.txt>
swat() {
  [ -f "$1/swat4j_mapped_methods.txt" ] && return
  mkdir -p "$1"
  (cd "$P" && python3 swat4j_mapping.py --libs-dir "$2" --jdk-lib "$3" --methods "$4" --output-dir "$1") \
    > "$1/run.log" 2>&1
}
jdk_dir() { find "$1"/JDK*_LIBS -name libjava.so -printf '%h\n' | head -1; }

# --- JDK 8 rebuilds: Groovy, Solr -------------------------------------------------
apps=() ov=()
for a in groovy_4.0.0-jdk8-buster solr_8.7.0-jdk8-buster; do
  L=$R/$a/Dataset/LIBS_$a
  swat "$HERE/syscall_ablation/swat4j_jdk8/$a" "$L" "$L/JDK8_LIBS/amd64" \
       "$R/$a/Bytecode_Analysis/outputs_$a/native_methods.txt"
  apps+=("$a=$R/$a"); ov+=("$a=$HERE/syscall_ablation/swat4j_jdk8/$a")
done
python3 audit_native_mapping.py --out out_jdk8_gs --app "${apps[@]}" --swat-override "${ov[@]}"

# --- Tomcat 11.0.18 (JDK 25) -------------------------------------------------------
T=tomcat_11.0.18-jdk25-temurin-noble
L=$F/$T/Dataset/LIBS_$T
swat "$HERE/syscall_ablation/swat4j_latest/tomcat_11.0.18" "$L" "$(jdk_dir "$L")" \
     "$F/$T/Bytecode_Analysis/outputs_$T/native_methods.txt"
python3 audit_native_mapping.py --out out_tomcat11 --app "tomcat_11.0.18=$F/$T" \
  --swat-override "tomcat_11.0.18=$HERE/syscall_ablation/swat4j_latest/tomcat_11.0.18"

# --- newer containers ---------------------------------------------------------------
# The audit locates Bytecode_Analysis/outputs_<label>, so the label is the folder name.
apps=() ov=()
for a in elasticsearch_7.1.0 jetty_latest solr_slim groovy_latest zookeeper_latest; do
  L=$F/$a/Dataset/LIBS_$a
  swat "$HERE/syscall_ablation/swat4j_latest/$a" "$L" "$(jdk_dir "$L")" \
       "$F/$a/Bytecode_Analysis/outputs_$a/native_methods.txt"
  apps+=("$a=$F/$a"); ov+=("$a=$HERE/syscall_ablation/swat4j_latest/$a")
done
python3 audit_native_mapping.py --out out_latest --app "${apps[@]}" --swat-override "${ov[@]}"
