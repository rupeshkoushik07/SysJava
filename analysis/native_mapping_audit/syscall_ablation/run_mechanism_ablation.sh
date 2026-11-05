#!/usr/bin/env bash
# Per-library, per-mechanism ablation over every app with a finished debug-symbol graph.
# Mapping audits: ../out (5 apps), ../out_c5, ../out_jdk8 (Jetty), ../out_jdk8_gs (Groovy, Solr),
# ../out_tomcat11 (Tomcat 11.0.18, JDK 25, FFM).
set -euo pipefail
cd "$(dirname "$0")"
python3 mechanism_ablation.py --out out_mech \
  --mapping ../out/per_method.csv ../out_c5/per_method.csv ../out_jdk8/per_method.csv ../out_jdk8_gs/per_method.csv ../out_tomcat11/per_method.csv \
  --app zookeeper_3.4.14=$HOME/Tutorial/EchoTrace/Final_results_JDK8/zookeeper_3.4.14/Binary_Analysis_symbolized/syscalls_output_zookeeper_3.4.14 \
        tomcat_7.0=$HOME/Tutorial/EchoTrace/Final_results_JDK8/tomcat_7.0/Binary_Analysis_symbolized/syscalls_output_tomcat_7.0 \
        cassandra_3.0.29=$HOME/Tutorial/EchoTrace/Final_results_JDK8/cassandra_3.0.29/Binary_Analysis_symbolized/syscalls_output_cassandra_3.0.29 \
        orientdb_3.2.19=$HOME/Tutorial/EchoTrace/Final_results_JDK8/orientdb_3.2.19/Binary_Analysis_symbolized/syscalls_output_orientdb_3.2.19 \
        jruby_9.4.2.0=$HOME/Tutorial/EchoTrace/Final_results_JDK8/jruby_9.4.2.0/Binary_Analysis_symbolized/syscalls_output_jruby_9.4.2.0 \
        cassandra_5.0.6-bookworm=$HOME/Tutorial/EchoTrace/Final_results_JDK8/cassandra_5.0.6-bookworm/Binary_Analysis_symbolized/syscalls_output_cassandra_5.0.6-bookworm \
        jetty_9.4.51-jdk8-buster=$HOME/Tutorial/EchoTrace/Final_results_JDK8/jetty_9.4.51-jdk8-buster/Binary_Analysis/syscalls_output_jetty_9.4.51-jdk8-buster \
        groovy_4.0.0-jdk8-buster=$HOME/Tutorial/EchoTrace/Final_results_JDK8/groovy_4.0.0-jdk8-buster/Binary_Analysis/syscalls_output_groovy_4.0.0-jdk8-buster \
        solr_8.7.0-jdk8-buster=$HOME/Tutorial/EchoTrace/Final_results_JDK8/solr_8.7.0-jdk8-buster/Binary_Analysis/syscalls_output_solr_8.7.0-jdk8-buster \
        tomcat_11.0.18=$HOME/Prototype/Final_results/tomcat_11.0.18-jdk25-temurin-noble/Binary_Analysis/syscalls_output_tomcat_11.0.18-jdk25-temurin-noble \
  --ffi groovy_4.0.0-jdk8-buster=$HOME/Tutorial/EchoTrace/Final_results_JDK8/groovy_4.0.0-jdk8-buster/Binary_Analysis/jna_ffi_analysis \
        tomcat_11.0.18=$HOME/Prototype/Final_results/tomcat_11.0.18-jdk25-temurin-noble/Binary_Analysis/jna_ffi_analysis
