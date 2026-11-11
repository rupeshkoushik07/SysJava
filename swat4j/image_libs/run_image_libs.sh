#!/bin/bash
# SWAT4J's static step (binary_analyser.py, unmodified) on each IMAGE's own libraries instead of the host's.
# Same as the paper run (../repo_libs_arm/static_2026-11-09, run_swat4j_host_out.sh) except:
#   1. the JDK: inside the per-app mount namespace the image's Temurin jre/lib/amd64 is bind-mounted over the
#      path SWAT4J hard-codes (rootfs/<T>/jdk_dynsym from extract_rootfs.sh: .symtab removed so the labels
#      look like Ubuntu's stripped JDK, which SWAT4J's parser needs; .text bytes identical),
#      /usr/lib/jvm/java-8-openjdk-amd64/jre/lib/amd64 (host: Ubuntu OpenJDK 8u504 at the paper run);
#   2. dependencies: bin/ldd comes first in PATH and resolves with the image's loader and library
#      directories (glibc 2.28 etc.) instead of the host's (glibc 2.35);
#   3. the bytecode step is not rerun: the native-method lists are the paper run's output-native files, so
#      only the libraries differ.
# Same datasets (datasets_2026-11-09: image LIBS + SWAT4J's repo JNI_thirdparty, MODE=replace).
#
# Usage: run_image_libs.sh [<image> ...]   (default: all ten)   Output: $OUT/output-syscalls/<name>_syscalls.txt
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
S="$(cd "$HERE/.." && pwd)"                         # .../swat4j
PAPER="${STATIC:-$S/jdk8_debian10/static}"
DATASETS="$PAPER/datasets"
OUT="${OUT:-$S/jdk8_debian10/image_libs}"
JDKDIR=/usr/lib/jvm/java-8-openjdk-amd64/jre/lib/amd64
ME="$(id -un)"
TARGETS=("$@"); [ ${#TARGETS[@]} -gt 0 ] || TARGETS=(zookeeper_3.4.14 tomcat_7.0 cassandra_3.0.29 jetty_9.4.51
  storm_2.4.0 orientdb_3.2.19 elasticsearch_7.5.2 solr_8.7.0 groovy_4.0.0 jruby_9.4.2.0)
mkdir -p "$OUT/output-native" "$OUT/output-syscalls" "$OUT/logs" "$OUT/work"

for t in "${TARGETS[@]}"; do
  app="${t%-jdk8-buster}-jdk8-buster"; name="${app%%_*}"
  libs="$DATASETS/$app/Dataset/LIBS_$app"
  root="$HERE/rootfs/$app"
  work="$OUT/work/$app"
  [ -d "$root$JDKDIR" ] || [ -d "$root/opt/java/jre/lib/amd64" ] || { echo "no rootfs for $app" >&2; exit 1; }
  rm -f "$OUT/logs/$app.ldd"; rm -rf "$work" && mkdir -p "$work/desktop" "$work/apr" "$work/output-native" "$work/output-syscalls"
  cp "$S"/run/*.py "$S"/run/*.sh "$work/"
  cp -r "$S/mrx_desktop/native" "$work/desktop/native"
  cp "$PAPER/output-native/${name}_native.txt" "$work/output-native/"
  cp "$PAPER/output-native/${name}_native.txt" "$OUT/output-native/"
  tc=$(ls "$libs"/libtcnative-1.so* 2>/dev/null | head -1 || true)
  [ -n "$tc" ] && cp "$tc" "$work/apr/libtcnative-1.so.0"
  (
    sudo unshare -m bash -c "
      mount --bind '$work/desktop' /home/mrx/Desktop
      mount --bind '$work/apr' /usr/local/apr/lib
      mount --bind '$root/jdk_dynsym' '$JDKDIR'
      sudo -u '$ME' env LANG=C.UTF-8 IMAGE_ROOT='$root' LDD_LOG='$OUT/logs/$app.ldd' PATH='$HERE/bin:$PATH' bash -c '
        set -e -o pipefail
        cd \"$work\"
        sh generate_all_jni_names.sh /home/mrx/Desktop
        echo \"ldd: \$(command -v ldd); JDK: \$(strings $JDKDIR/server/libjvm.so | grep -m1 \"^1.8.0_\")\"
        echo \"=== [2/2] binary analysis (image libraries) ===\"
        python3 -u binary_analyser.py \"$libs\" output-native/${name}_native.txt
      '
    " > "$OUT/logs/$app.log" 2>&1 || true
    cp "$work/output-syscalls/${name}_syscalls.txt" "$OUT/output-syscalls/" 2>/dev/null || true
    echo "[done] $app -> $(wc -l < "$OUT/output-syscalls/${name}_syscalls.txt" 2>/dev/null || echo FAILED) syscalls"
  ) &
done
wait
