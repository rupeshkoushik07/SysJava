#!/usr/bin/env bash
#
# Reproduce Table tab:latest (newer images, JDK 8-25): full SysJava pipeline per
# image, then the table. Run ../setup.sh first.
#
#   ./reproduce.sh                      # all 10 images, one after another
#   ./reproduce.sh tomcat_11.0.22 ...   # selected images
#   STAGE=8 ./reproduce.sh solr_10.0.0  # resume one image from a stage (1-11)
#   TABLE_ONLY=1 ./reproduce.sh         # rebuild the table from existing results
#
# Results:  ../work/latest/Final_results_latest_versions/<image>/
# Table:    tables_rerun/table.{md,csv} and table_rows.tex
# Needs:    ~8 cores, 64 GB RAM (+ swap), ~60 GB disk; a full libjvm SysPart run
#           takes 20-35 GB and 1-3 h. One image takes 2-8 h end to end.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
W="$HERE/../work/latest"
[ -d "$W/scripts" ] || { echo "run ../setup.sh first"; exit 1; }
ALL=(cassandra_5.0.8 zookeeper_3.9.5 tomcat_11.0.22 solr_10.0.0 groovy_5.0.6
     orientdb_3.2.53 jetty_12.1.10 elasticsearch_7.1.0 storm_2.8.8 jruby_10.1.0.0)
TARGETS=("$@"); [ ${#TARGETS[@]} -gt 0 ] || TARGETS=("${ALL[@]}")

# sysdig_unified.sh names its output after the IMAGE TAG, so each image is
# tagged with its version. ../docker_images/images.tsv pins every tag to the digest used for the
# shipped results; the image is pulled by digest and tagged locally.
pin() {
    local tag="$1" ref
    docker image inspect "$tag" >/dev/null 2>&1 && return 0
    ref="$(awk -F'\t' -v t="$tag" '$1==t{print $2}' "$HERE/../docker_images/images.tsv")"
    case "$ref" in *@sha256:*) docker pull "$ref" && docker tag "$ref" "$tag" ;;
                   *) docker pull "$tag" ;; esac
}
if [ -z "${TABLE_ONLY:-}" ]; then
    for t in "${TARGETS[@]}"; do pin "${t%%_*}:${t#*_}"; done
    [[ " ${TARGETS[*]} " == *" storm_2.8.8 "* ]] && pin zookeeper:3.9.5
    for t in "${TARGETS[@]}"; do
        echo "===== $t"
        (cd "$W" && bash scripts/run_latest_target.sh "$t" "${STAGE:-1}") \
            || echo "!! $t exited $? (see $W/Final_results_latest_versions/$t/pipeline_run.log)"
    done
fi

python3 "$HERE/../tools/make_tables.py" latest "$W/Final_results_latest_versions" \
    --runtime "$W/runc.txt" --out "$HERE/tables_rerun" \
    ${AUDIT:+--audit "$AUDIT"}
echo "Compare with the shipped results: diff -r tables/ tables_rerun/"
