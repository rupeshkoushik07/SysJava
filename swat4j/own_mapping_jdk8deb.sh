#!/bin/bash
# SWAT4J's own native-method mapping, counted per image after run_static_jdk8deb.sh: SWAT4J prints
# no per-method counts, so count_own_mapping.py imports its unmodified binary_analyser.py from the
# image's work folder and replays its mapping on the native methods JTracer found
# (output-native/<app>_native.txt). It runs in the same mount namespace as the static run
# (/home/mrx/Desktop and /usr/local/apr/lib bind-mounted from the work folder).
#
#   own_mapping_jdk8deb.sh [target ...]        (default: the ten)
#   STATIC=<dir>   the static run (default jdk8_debian10/static)
#   OUT=<dir>      default jdk8_debian10/own_mapping: <app>.tsv (method, strategy, symbol, library), summary.txt
# Needs sudo.
set -euo pipefail
H="$(cd "$(dirname "$0")" && pwd)"
STATIC="${STATIC:-$H/jdk8_debian10/static}"
OUT="${OUT:-$H/jdk8_debian10/own_mapping}"
ME="$(id -un)"
TARGETS=("$@"); [ ${#TARGETS[@]} -gt 0 ] || TARGETS=(zookeeper_3.4.14 tomcat_7.0 cassandra_3.0.29 jetty_9.4.51
  storm_2.4.0 orientdb_3.2.19 elasticsearch_7.5.2 solr_8.7.0 groovy_4.0.0 jruby_9.4.2.0)
mkdir -p "$OUT"
for t in "${TARGETS[@]%-jdk8-buster}"; do
  T=$t-jdk8-buster; app=${t%%_*}
  W=$STATIC/work/$T; LIBS=$STATIC/datasets/$T/Dataset/LIBS_$T
  [ -f "$STATIC/output-native/${app}_native.txt" ] || { echo "$T: no static run in $STATIC"; exit 1; }
  sudo unshare -m bash -c "
    mount --bind '$W/desktop' /home/mrx/Desktop
    mount --bind '$W/apr' /usr/local/apr/lib
    sudo -u '$ME' python3 '$H/count_own_mapping.py' '$W' '$LIBS' '$STATIC/output-native/${app}_native.txt' '$OUT' '$app'"
done | tee "$OUT/summary.txt"
