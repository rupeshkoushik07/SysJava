#!/bin/bash
# SWAT4J static analysis (unmodified, run/ from setup_swat4j.sh) on the ten JDK 8 Debian 10 images,
# as for the paper (2026-11-09). Each image gets the JARs and native libraries SysJava captured from
# its container, plus the six libraries of SWAT4J's own repository (run/JNI_thirdparty/), the
# repository copy winning on a name clash: that is what the original SWAT4J did by reading them from
# /home/mrx/Desktop/so. The version we run reads them from the image's LIBS folder under fixed names:
# Netty epoll, JFFI and the 32-bit Sigar, and tomcat-native through /usr/local/apr/lib, which
# run_swat4j_host_out.sh fills from LIBS. Hadoop and RocksDB are never read. SWAT4J finds its own
# native methods (JTracer); SysJava's list is not given to it.
#
#   run_static_jdk8deb.sh [target ...]            (default: the ten; e.g. zookeeper_3.4.14)
#
#   ET=<dir>   SysJava results with <image>/Dataset/ (a SysJava rerun, work/jdk8/Final_results_JDK8);
#              default: the shipped capture, unpacked from
#              ../2_swat4j_vs_sysjava/sysjava_results/<image>/dataset/ (the same JARs and libraries)
#   OUT=<dir>  default jdk8_debian10/static: output-native/, output-syscalls/, logs/, work/<image>/;
#              the datasets SWAT4J reads are in <OUT>/datasets/<image>/Dataset
# Needs sudo (mount namespace per image, see run_swat4j_host_out.sh) and OpenJDK 8.
set -euo pipefail
H="$(cd "$(dirname "$0")" && pwd)"
SHIPPED="$H/../2_swat4j_vs_sysjava/sysjava_results"
ET="${ET:-}"
OUT="${OUT:-$H/jdk8_debian10/static}"
REPO_LIBS="$H/run/JNI_thirdparty"
[ -d "$REPO_LIBS" ] || { echo "$REPO_LIBS missing: run setup_swat4j.sh first"; exit 1; }
TARGETS=("$@"); [ ${#TARGETS[@]} -gt 0 ] || TARGETS=(zookeeper_3.4.14 tomcat_7.0 cassandra_3.0.29 jetty_9.4.51
  storm_2.4.0 orientdb_3.2.19 elasticsearch_7.5.2 solr_8.7.0 groovy_4.0.0 jruby_9.4.2.0)
TARGETS=("${TARGETS[@]%-jdk8-buster}")
for t in "${TARGETS[@]}"; do
  T=$t-jdk8-buster
  if [ -n "$ET" ]; then
    src=$ET/$T/Dataset
  else
    src=$OUT/capture/$T/Dataset
    if [ ! -d "$src" ]; then
      mkdir -p "$OUT/capture/$T"
      cat "$SHIPPED/$T"/dataset/Dataset.tar.xz.part* | xz -dc | tar -x -C "$OUT/capture/$T"
    fi
  fi
  [ -d "$src/LIBS_$T" ] || { echo "$T: no dataset at $src"; exit 1; }
  d=$OUT/datasets/$T/Dataset; rm -rf "$OUT/datasets/$T"; mkdir -p "$d"
  ln -s "$src/JARFILES_$T" "$d/JARFILES_$T"
  cp -a "$src/LIBS_$T" "$d/LIBS_$T"
  cp --remove-destination "$REPO_LIBS"/* "$d/LIBS_$T/"
  echo "$T: dataset from $src + run/JNI_thirdparty"
done
DATASETS="$OUT/datasets" OUT="$OUT" bash "$H/run_swat4j_host_out.sh" "${TARGETS[@]/%/-jdk8-buster}"
