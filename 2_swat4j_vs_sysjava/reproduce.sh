#!/usr/bin/env bash
#
# Reproduce Table tab:results: SysJava vs SWAT4J on ten JDK 8 images, each rebuilt
# on Debian 10 + Temurin 8 (*-jdk8-buster). One command runs both tools and prints
# the table. Run ../setup.sh first.
#
#   ./reproduce.sh                              # SysJava + SWAT4J on all ten, then the table
#   ./reproduce.sh jetty_9.4.51-jdk8-buster     # one image
#   STAGE=7 ./reproduce.sh solr_8.7.0-jdk8-buster   # resume SysJava from a stage
#   SKIP_SYSJAVA=1 ./reproduce.sh               # only SWAT4J (needs a SysJava rerun's Dataset/)
#   SKIP_SWAT4J=1  ./reproduce.sh               # only SysJava
#   TABLE_ONLY=1   ./reproduce.sh               # only the table, from the shipped outputs
#
# 1. SysJava, full pipeline per image   -> ../work/jdk8/Final_results_JDK8/<image>/
# 2. SWAT4J, unmodified (../swat4j/README.md): static on the same JARs and libraries,
#    dynamic with strace on containerd (needs sudo) -> ../swat4j/jdk8_debian10/
# 3. Table: SysJava (A), SWAT4J static + dynamic (B), A ∩ B, A ∖ B, B ∖ A
#    -> tables_rerun/swat4j_outputs/ and the printed table
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ART="$HERE/.."
W="$ART/work/jdk8"
SW="$ART/swat4j"
ALL=(zookeeper_3.4.14-jdk8-buster tomcat_7.0-jdk8-buster cassandra_3.0.29-jdk8-buster
     jetty_9.4.51-jdk8-buster storm_2.4.0-jdk8-buster orientdb_3.2.19-jdk8-buster
     elasticsearch_7.5.2-jdk8-buster solr_8.7.0-jdk8-buster groovy_4.0.0-jdk8-buster
     jruby_9.4.2.0-jdk8-buster)
TARGETS=("$@"); [ ${#TARGETS[@]} -gt 0 ] || TARGETS=("${ALL[@]}")

if [ -n "${TABLE_ONLY:-}" ]; then
    python3 "$SW/show_results.py" "$SW/outputs" ${SETS:+--sets}
    exit 0
fi

# ------------------------------------------------------------- 1. SysJava
if [ -z "${SKIP_SYSJAVA:-}" ]; then
    [ -d "$W/scripts" ] || { echo "run ../setup.sh first"; exit 1; }
    for t in "${TARGETS[@]}"; do
        app="${t%%_*}"; ver="${t#*_}"; ver="${ver%-jdk8-buster}"
        docker image inspect "${app}:${ver}-jdk8-buster" >/dev/null 2>&1 \
            || bash "$ART/docker_images/build_jdk8_images.sh" "$app"
    done
    for t in "${TARGETS[@]}"; do
        echo "===== SysJava: $t"
        (cd "$W" && bash scripts/run_jdk8_target.sh "$t" "${STAGE:-1}") \
            || echo "!! $t exited $? (see $W/Final_results_JDK8/$t/pipeline_run.log)"
    done
fi
SJ="$W/Final_results_JDK8"

# -------------------------------------------------------------- 2. SWAT4J
if [ -z "${SKIP_SWAT4J:-}" ]; then
    [ -d "$SW/run" ] || bash "$SW/setup_swat4j.sh"
    apps=(); for t in "${TARGETS[@]}"; do apps+=("${t%%_*}"); done
    echo "===== SWAT4J static: ${apps[*]}"
    DATASETS="$SJ" OUT="$SW/jdk8_debian10/static_host" bash "$SW/run_swat4j_host_out.sh" "${TARGETS[@]}"
    echo "===== SWAT4J dynamic: ${apps[*]}"
    bash "$SW/dynamic_all_jdk8deb.sh" "${apps[@]}"
fi

# --------------------------------------------------------------- 3. table
ET="$SJ" bash "$SW/package_outputs_jdk8deb.sh" "$HERE/tables_rerun/swat4j_outputs"
python3 "$SW/show_results.py" "$HERE/tables_rerun/swat4j_outputs" ${SETS:+--sets}
echo "Compare with the shipped outputs: python3 ../swat4j/show_results.py ../swat4j/outputs"
