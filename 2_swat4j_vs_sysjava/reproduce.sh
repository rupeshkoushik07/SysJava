#!/usr/bin/env bash
#
# Reproduce Table tab:results: SysJava vs SWAT4J on ten JDK 8 images (five
# rebuilt on Debian 10 + Temurin 8, five official images that ship JDK 8).
# One command runs both tools and prints the finished table. Run ../setup.sh first.
#
#   ./reproduce.sh                               # SysJava (SysPart) + SWAT4J on all ten, then the tables
#   ./reproduce.sh jetty_9.4.51-jdk8-buster      # one image
#   STAGE=7 ./reproduce.sh solr_8.7.0-jdk8-buster   # resume SysJava from a stage
#   SKIP_SYSJAVA=1 ./reproduce.sh                # only SWAT4J, then the tables
#   SKIP_SWAT4J=1  ./reproduce.sh                # only SysJava, then the tables
#   TABLE_ONLY=1 ./reproduce.sh                  # only the tables, from existing results
#
# 1. SysJava: full pipeline per image (capture, bytecode analysis, SysPart, profile)
#             -> ../work/jdk8/Final_results_JDK8/<image>/
# 2. SWAT4J, unmodified (../swat4j/README.md):
#      static  (JTracer on the JARs and libraries SysJava extracted)
#             -> ../swat4j/rerun_host/output-syscalls/<app>_syscalls.txt
#      dynamic (strace on containerd while the official image starts; needs sudo)
#             -> ../swat4j/dynamic/<app>_result.txt, timing.csv
# 3. Tables in tables_rerun/:
#      table.{md,csv}, table_rows.tex       SysJava rows (make_tables.py)
#      sysjava_vs_swat4j.{md,tex}           the comparison: A, B, A∩B, A∖B, B∖A
#    With TABLE_ONLY=1 the tables use the shipped results for any part that was
#    not rerun (shipped SysJava results in sysjava_results/, shipped SWAT4J lists
#    in ../swat4j/outputs/).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ART="$HERE/.."
W="$ART/work/jdk8"
SW="$ART/swat4j"
ALL=(storm_2.4.0-jdk8-buster solr_8.7.0-jdk8-buster elasticsearch_7.5.2-jdk8-buster
     groovy_4.0.0-jdk8-buster jetty_9.4.51-jdk8-buster
     zookeeper_3.4.14 tomcat_7.0 cassandra_3.0.29 orientdb_3.2.19 jruby_9.4.2.0)
TARGETS=("$@"); [ ${#TARGETS[@]} -gt 0 ] || TARGETS=("${ALL[@]}")
[ -n "${TABLE_ONLY:-}" ] && SKIP_SYSJAVA=1 SKIP_SWAT4J=1

pin() {  # <tag>: pull by the digest in images.tsv, tag locally
    local tag="$1" ref
    docker image inspect "$tag" >/dev/null 2>&1 && return 0
    ref="$(awk -F'\t' -v t="$tag" '$1==t{print $2}' "$ART/docker_images/images.tsv")"
    case "$ref" in *@sha256:*) docker pull "$ref" && docker tag "$ref" "$tag" ;; *) docker pull "$tag" ;; esac
}

# ------------------------------------------------------------- 1. SysJava
if [ -z "${SKIP_SYSJAVA:-}" ]; then
    [ -d "$W/scripts" ] || { echo "run ../setup.sh first"; exit 1; }
    # The *-jdk8-buster images are rebuilt (official app layout on Debian 10 +
    # Temurin 8u504-b01); the official JDK 8 images are pulled by digest.
    for t in "${TARGETS[@]}"; do
        if [[ "$t" == *-jdk8-buster ]]; then
            app="${t%%_*}"; ver="${t#*_}"; ver="${ver%-jdk8-buster}"
            docker image inspect "${app}:${ver}-jdk8-buster" >/dev/null 2>&1 \
                || bash "$ART/docker_images/build_jdk8_images.sh" "$app"
        else
            pin "${t%%_*}:${t#*_}"
        fi
    done
    [[ " ${TARGETS[*]} " == *" storm_2.4.0-jdk8-buster "* ]] && pin zookeeper:3.7
    for t in "${TARGETS[@]}"; do
        echo "===== SysJava: $t"
        (cd "$W" && bash scripts/run_jdk8_target.sh "$t" "${STAGE:-1}") \
            || echo "!! $t exited $? (see $W/Final_results_JDK8/$t/pipeline_run.log)"
    done
fi

# Which SysJava results the tables use: the rerun when there is one, else shipped.
SJ="$W/Final_results_JDK8"
if [ ! -d "$SJ" ] || [ -z "$(ls -A "$SJ" 2>/dev/null)" ]; then SJ="$HERE/sysjava_results"; fi

# -------------------------------------------------------------- 2. SWAT4J
if [ -z "${SKIP_SWAT4J:-}" ]; then
    [ -d "$SW/run" ] || bash "$SW/setup_swat4j.sh"
    apps=(); for t in "${TARGETS[@]}"; do apps+=("${t%%_*}"); done
    echo "===== SWAT4J static: ${apps[*]}"
    # Same JARs and libraries as SysJava: each image's Dataset/, which a SysJava
    # rerun creates (the shipped results do not include it).
    DATASETS="$SJ" bash "$SW/run_swat4j_host.sh" "${TARGETS[@]}"
    echo "===== SWAT4J dynamic: ${apps[*]}"
    for a in "${apps[@]}"; do
        img="$(awk -F'|' -v a="$a" '$1==a{print $2}' "$SW/dynamic_swat4j.sh")"
        [ -n "$img" ] && pin "$img"
    done
    bash "$SW/dynamic_swat4j.sh" "${apps[@]}"
fi

# -------------------------------------------------------------- 3. tables
pick() {  # <rerun dir> <shipped dir> <file that must exist>: rerun if it has results
    if [ -e "$1/$3" ]; then echo "$1"; else echo "$2"; fi
}
STATIC="$(pick "$SW/rerun_host/output-syscalls" "$SW/outputs/static_host/output-syscalls" zookeeper_syscalls.txt)"
DYNAMIC="$(pick "$SW/dynamic" "$SW/outputs/dynamic" timing.csv)"
echo
echo "SysJava results: $SJ"
echo "SWAT4J static:   $STATIC"
echo "SWAT4J dynamic:  $DYNAMIC"

RUNTIME=("$HERE/runc.txt" "$HERE/runc_host_1.3.4_additions.txt")
python3 "$ART/tools/make_tables.py" jdk8 "$SJ" --runtime "${RUNTIME[@]}" \
    --out "$HERE/tables_rerun" ${AUDIT:+--audit "$AUDIT"}
echo
echo "===== Table tab:results: SysJava vs SWAT4J"
python3 "$ART/tools/swat4j_table.py" "$SJ" "$STATIC" "$DYNAMIC" "$HERE/tables_rerun/sysjava_vs_swat4j"
echo
echo "Tables: $HERE/tables_rerun/  (compare with the shipped tables/: diff -r tables/ tables_rerun/)"
