#!/usr/bin/env bash
#
# Reproduce the SysJava side of Table tab:results (ten JDK 8 images: five rebuilt
# on Debian 10 + Temurin 8, five official images that ship JDK 8), then the
# SWAT4J side. Run ../setup.sh first.
#
#   ./reproduce.sh                               # build images, run all five, tables
#   ./reproduce.sh jetty_9.4.51-jdk8-buster      # one image
#   STAGE=7 ./reproduce.sh solr_8.7.0-jdk8-buster
#   TABLE_ONLY=1 ./reproduce.sh
#   SWAT4J=1 ./reproduce.sh                      # also rerun SWAT4J (static + dynamic)
#
# Results:  ../work/jdk8/Final_results_JDK8/<image>/
# Table:    tables_rerun/table.{md,csv}; SWAT4J comparison in ../swat4j/
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ART="$HERE/.."
W="$ART/work/jdk8"
[ -d "$W/scripts" ] || { echo "run ../setup.sh first"; exit 1; }
ALL=(storm_2.4.0-jdk8-buster solr_8.7.0-jdk8-buster elasticsearch_7.5.2-jdk8-buster
     groovy_4.0.0-jdk8-buster jetty_9.4.51-jdk8-buster
     zookeeper_3.4.14 tomcat_7.0 cassandra_3.0.29 orientdb_3.2.19 jruby_9.4.2.0)
TARGETS=("$@"); [ ${#TARGETS[@]} -gt 0 ] || TARGETS=("${ALL[@]}")

if [ -z "${TABLE_ONLY:-}" ]; then
    # 1. Rebuild the *-jdk8-buster images (official app layout on Debian 10 +
    #    Temurin 8u); pull the official JDK 8 images by the digest in images.tsv.
    for t in "${TARGETS[@]}"; do
        if [[ "$t" != *-jdk8-buster ]]; then
            tag="${t%%_*}:${t#*_}"
            docker image inspect "$tag" >/dev/null 2>&1 && continue
            ref="$(awk -F'\t' -v t="$tag" '$1==t{print $2}' "$HERE/../docker_images/images.tsv")"
            case "$ref" in *@sha256:*) docker pull "$ref" && docker tag "$ref" "$tag" ;; *) docker pull "$tag" ;; esac
            continue
        fi
        app="${t%%_*}"; ver="${t#*_}"; ver="${ver%-jdk8-buster}"
        docker image inspect "${app}:${ver}-jdk8-buster" >/dev/null 2>&1 \
            || bash "$ART/docker_images/build_jdk8_images.sh" "$app"   # pinned base + Temurin 8u504-b01
    done
    # 2. Pipeline per image (storm also starts ZooKeeper on et-jdk8-net).
    for t in "${TARGETS[@]}"; do
        echo "===== $t"
        (cd "$W" && bash scripts/run_jdk8_target.sh "$t" "${STAGE:-1}") \
            || echo "!! $t exited $? (see $W/Final_results_JDK8/$t/pipeline_run.log)"
    done
fi

# 3. SysJava rows.
python3 "$ART/tools/make_tables.py" jdk8 "$W/Final_results_JDK8" \
    --runtime "$W/runc.txt" --out "$HERE/tables_rerun" ${AUDIT:+--audit "$AUDIT"}

# 4. SWAT4J (unmodified upstream tool; see ../swat4j/README.md for its one-time
#    build into ../swat4j/run/). Static analysis on the same datasets, dynamic
#    analysis (strace on containerd) on the official images as in the SWAT4J paper.
if [ -n "${SWAT4J:-}" ]; then
    DATASETS="$W/Final_results_JDK8" bash "$ART/swat4j/run_swat4j_host.sh" "${TARGETS[@]}"
    bash "$ART/swat4j/dynamic_swat4j.sh" $(for t in "${TARGETS[@]}"; do echo "${t%%_*}"; done)
    echo "SWAT4J allowlists: $ART/swat4j/rerun_host/output-syscalls/ and $ART/swat4j/dynamic/"
fi
echo "Compare with the shipped results: diff -r tables/ tables_rerun/"
