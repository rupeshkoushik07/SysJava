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
#   mapping/<app>.tsv                 SWAT4J's own JNI mapping of its own JTracer list (count_own_mapping.py)
#   dynamic/<app>_result.txt          SWAT4J dynamic allowlist (strace -f -c on containerd, clean run)
#   dynamic/<app>_strace.txt, <app>.log, timing.csv, dynamic_runs.tsv
#   sysjava/<app>.txt                 SysJava allowlist (SCMP_ACT_ALLOW names of the profile)
#   sysjava/SOURCE.tsv                profile path and runtime-check RESULT per image
set -euo pipefail
H="$(cd "$(dirname "$0")" && pwd)"
J=$H/jdk8_debian10
# SWAT4J static + mapping: the run with its repository's JNI_thirdparty/ libraries (as the original)
R=${STATIC:-$J/static}; RM=${MAPPING:-$J/own_mapping}
# static allowlists: binary_analyser.py on each image's own libraries (image_libs/run_image_libs.sh)
RI=${IMAGE_STATIC:-$J/image_libs}
ET=${ET:-$H/../2_swat4j_vs_sysjava/sysjava_results}
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
  cp "$R/output-native/${app}_native.txt" "$OUT/static/native_methods/$app.txt"
  cp "$RI/output-syscalls/${app}_syscalls.txt" "$OUT/static/syscalls/$app.txt"
  [ ! -f "$RI/logs/$img.log" ] || scrub < "$RI/logs/$img.log" | xz > "$OUT/static/logs/$img.log.xz"
  [ ! -f "$RM/$app.tsv" ] || cp "$RM/$app.tsv" "$OUT/mapping/"
  for f in "${app}_result.txt" "${app}_strace.txt" "$app.log"; do
    [ ! -f "$J/dynamic/$f" ] || cp "$J/dynamic/$f" "$OUT/dynamic/"
  done
  # SysJava: only a finished pipeline counts
  log=$ET/$img/pipeline_run.log; prof=$ET/$img/Binary_Analysis/syscalls_output_$img/$img.json
  if [ -f "$log" ] && tail -1 "$log" | grep -q "stage done: finished" && [ -f "$prof" ]; then
    python3 -c "import json,sys; r=json.load(open(sys.argv[1]))['syscalls']; \
print('\n'.join(sorted(set().union(*[set(x['names']) for x in r if x.get('action')=='SCMP_ACT_ALLOW']) - set(sys.argv[2:]))))" \
      "$prof" $([ "$app" = storm ] && echo sync) > "$OUT/sysjava/$app.txt"   # storm: sync only from false FFM hits
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
