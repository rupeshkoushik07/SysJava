#!/bin/bash
# SWAT4J dynamic (strace -f -c on containerd) for the 10 JDK 8 Debian 10 images, one at a
# time. strace -f also follows any other container started meanwhile, so each run's window
# is checked with `docker events`; a run during which another container started is redone
# (up to 3 tries) and the outcome is logged in dynamic_runs.tsv.
H="$(cd "$(dirname "$0")" && pwd)"; OUT=$H/jdk8_debian10/dynamic; mkdir -p $OUT
LOG=$OUT/dynamic_runs.tsv; [ -f $LOG ] || printf 'app\ttry\tstart\tend\tother_container_starts\tresult\n' > $LOG
docker inspect et-jdk8-zookeeper >/dev/null 2>&1 || echo "WARNING: et-jdk8-zookeeper missing (storm needs it)"
for app in ${*:-zookeeper tomcat cassandra jetty storm orientdb elasticsearch solr groovy jruby}; do
  for try in 1 2 3; do
    until [ "$(free -g | awk '/^Mem:/{print $7}')" -ge 30 ]; do sleep 60; done
    t0=$(date +%s); OUT=$OUT bash $H/dynamic_swat4j_jdk8deb.sh $app; t1=$(date +%s)
    others=$(docker events --since $t0 --until $((t1 + 1)) --filter event=start --format '{{.Actor.Attributes.name}}' | grep -v "^swat4j_dyn_$app$" | tr '\n' ' ')
    res=$(tail -1 $OUT/timing.csv)
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' $app $try "$(date -d @$t0 +%T)" "$(date -d @$t1 +%T)" "${others:-none}" "$res" >> $LOG
    [ -z "$others" ] && break
    echo "$app try $try: other containers started ($others); retrying in 5 min"; sleep 300
  done
done
echo "$(date +%T) dynamic done"
