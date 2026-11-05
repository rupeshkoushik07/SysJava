#!/usr/bin/env bash
# Mode B of the Confine comparison: SysPart with every library's exported
# functions as start functions (no JNI binding), for all 11 Java targets.
# Waits for the current mode-A rerun to finish so the 8 cores aren't oversubscribed.
set -u
cd "$(dirname "$0")/.."
while pgrep -f "rerun_syspart_symbolized.sh elasticsearch" >/dev/null; do sleep 60; done
START_MODE=exports RESUME=1 PHASE=all JOBS=3 JOB_MEM_GB=28 JOB_TIMEOUT=7200 \
    bash scripts/rerun_syspart_symbolized.sh cassandra_3.0.29 cassandra_5.0.6-bookworm elasticsearch_7.5.2 \
    groovy_4.0.0 jetty_9.4.51 jruby_9.4.2.0 orientdb_3.2.19 solr_8.7.0 storm_2.4.0 tomcat_7.0 zookeeper_3.4.14
