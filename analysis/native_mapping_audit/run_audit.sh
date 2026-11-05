#!/usr/bin/env bash
# Reproduces every number in RQ1_NATIVE_MAPPING.md.
#
# Primary set = the JDK 8 images whose denominators appear in the submitted
# Table I. Jetty 9.4.51 has no JDK 8 mapping output on disk; its JDK 17 run is
# used and flagged in the report.
set -euo pipefail
cd "$(dirname "$0")"
P=${PROTOTYPE:-$HOME/Prototype}
E=$P/Final_results_echotrace
F=$P/Final_results

# OrientDB never had per-method SWAT4J output; regenerate it (container JDK 8 libs,
# because the host JDK 8 used for the other reruns is no longer installed).
if [ ! -f swat4j_rerun_orientdb/swat4j_mapped_methods.txt ]; then
  L=$E/orientdb_3.2.19/Dataset/LIBS_orientdb_3.2.19
  mkdir -p swat4j_rerun_orientdb
  (cd "$P" && python3 swat4j_mapping.py --libs-dir "$L" --jdk-lib "$L/JDK8_LIBS/amd64" \
      --methods "$E/orientdb_3.2.19/Bytecode_Analysis/outputs_orientdb_3.2.19/native_methods.txt" \
      --output-dir "$OLDPWD/swat4j_rerun_orientdb") > swat4j_rerun_orientdb/run.log 2>&1
fi

python3 audit_native_mapping.py --out out \
  --app zookeeper_3.4.14=$E/zookeeper_3.4.14 \
        tomcat_7.0=$E/tomcat_7.0 \
        cassandra_3.0.29=$E/cassandra_3.0.29 \
        jetty_9.4.51=$E/jetty_9.4.51 \
        storm_2.4.0=$F/storm-2.4.0-temurin8_latest \
        orientdb_3.2.19=$E/orientdb_3.2.19 \
        elasticsearch_7.5.2=$F/local_elasticsearch_7.5.2-temurin8-buster \
        solr_8.7.0=$F/local_solr_8.7.0-temurin8-buster \
        groovy_4.0.0=$F/local_groovy_4.0.0-temurin8-buster \
        jruby_9.4.2.0=$E/jruby_9.4.2.0 \
  --swat-override orientdb_3.2.19="$PWD/swat4j_rerun_orientdb"

# Independent evidence (class-file descriptors, RegisterNatives rows, runtime
# trace), exhaustive overload / platform checks, then the sample verdicts.
python3 collect_sample_evidence.py
python3 platform_check.py
python3 adjudicate_sample.py
