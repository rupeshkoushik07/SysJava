#!/usr/bin/env bash
# Collect everything SWAT4J produced for the ten JDK 8 Debian 10 images (*-jdk8-buster), plus
# SysJava's allowlists for the same images, into one folder that show_results.py reads.
# Nothing is rerun; this only copies.
#
#   package_outputs_jdk8deb.sh [out_dir]      (default: ./outputs_jdk8_debian10)
#
# Layout of out_dir:
#   static/native_methods/<app>.txt   native methods JTracer found (SWAT4J bytecode analysis)
#   static/syscalls/<app>.txt         SWAT4J static allowlist (binary_analyser.py)
#   static/logs/<image>.log.xz        SWAT4J static run log
#   mapping/<image>/                  swat4j_mapping.py on SysJava's native_methods.txt
#   dynamic/<app>_result.txt          SWAT4J dynamic allowlist (strace -f -c on containerd, clean run)
#   dynamic/<app>_strace.txt, <app>.log, timing.csv, dynamic_runs.tsv
#   sysjava/<app>.txt                 SysJava allowlist (SCMP_ACT_ALLOW names of the profile)
#   sysjava/SOURCE.tsv                profile path and runtime-check RESULT per image
set -euo pipefail
H="$(cd "$(dirname "$0")" && pwd)"
J=$H/jdk8_debian10
ET=${ET:-$HOME/Tutorial/EchoTrace/Final_results_JDK8}
OUT="${1:-$H/outputs_jdk8_debian10}"
TARGETS="zookeeper_3.4.14 tomcat_7.0 cassandra_3.0.29 jetty_9.4.51 storm_2.4.0 orientdb_3.2.19
         elasticsearch_7.5.2 solr_8.7.0 groovy_4.0.0 jruby_9.4.2.0"

# home directory and user name are replaced in every copied text file (the artifact is anonymous)
scrub() { sed -e "s#$HOME#~#g" -e "s#$(id -un)#user#g"; }

rm -rf "$OUT"
mkdir -p "$OUT"/static/{native_methods,syscalls,logs} "$OUT"/mapping "$OUT"/dynamic "$OUT"/sysjava
printf 'app\timage\tprofile\tresult\n' > "$OUT/sysjava/SOURCE.tsv"
for t in $TARGETS; do
  app=${t%%_*}; img=$t-jdk8-buster
  cp "$J/static_host/output-native/${app}_native.txt" "$OUT/static/native_methods/$app.txt"
  cp "$J/static_host/output-syscalls/${app}_syscalls.txt" "$OUT/static/syscalls/$app.txt"
  [ ! -f "$J/static_host/logs/$img.log" ] || scrub < "$J/static_host/logs/$img.log" | xz > "$OUT/static/logs/$img.log.xz"
  if [ -d "$J/mapping/$img" ]; then
    cp -r "$J/mapping/$img" "$OUT/mapping/"
    [ ! -f "$J/mapping/$img.log" ] || cp "$J/mapping/$img.log" "$OUT/mapping/"
  fi
  for f in "${app}_result.txt" "${app}_strace.txt" "$app.log"; do
    [ ! -f "$J/dynamic/$f" ] || cp "$J/dynamic/$f" "$OUT/dynamic/"
  done
  # SysJava: only a finished pipeline counts
  log=$ET/$img/pipeline_run.log; prof=$ET/$img/Binary_Analysis/syscalls_output_$img/$img.json
  if [ -f "$log" ] && tail -1 "$log" | grep -q "stage done: finished" && [ -f "$prof" ]; then
    python3 -c "import json,sys; r=json.load(open(sys.argv[1]))['syscalls']; \
print('\n'.join(sorted(set().union(*[set(x['names']) for x in r if x.get('action')=='SCMP_ACT_ALLOW']))))" \
      "$prof" > "$OUT/sysjava/$app.txt"
    res=$(grep -E '^RESULT=' "$log" | tail -1 | cut -d= -f2)
  else
    res=pending
  fi
  printf '%s\t%s\t%s\t%s\n' "$app" "$img" "${prof#$HOME/}" "${res:-unknown}" >> "$OUT/sysjava/SOURCE.tsv"
done
cp "$J/dynamic/timing.csv" "$J/dynamic/dynamic_runs.tsv" "$OUT/dynamic/"
cp "$H/README_outputs_jdk8deb.md" "$OUT/README.md"
ml=$ET/elasticsearch_7.5.2-jdk8-buster/extra_components/ml_component_imports/README.md
[ ! -f "$ml" ] || cp "$ml" "$OUT/sysjava/elasticsearch_ml_component_imports.md"
find "$OUT" -type f ! -name '*.xz' -exec grep -Il . {} + | while read -r f; do
  scrub < "$f" > "$f.tmp" && mv "$f.tmp" "$f"
done
! grep -rIq -e "$(id -un)" "$OUT" || { echo "user name left in $OUT" >&2; exit 1; }
du -sh "$OUT"
