#!/bin/bash
# Run SWAT4J (facumolina HEAD, unmodified) directly on the host (Ubuntu 22.04) with OpenJDK 8
# at /usr/lib/jvm/java-8-openjdk-amd64, on EchoTrace's container datasets.
# Each app runs in its own mount namespace so SWAT4J's hardcoded /home/mrx/Desktop and
# /usr/local/apr/lib are private per app (SWAT4J rewrites soname/ on every run).
#
# Usage: run_swat4j_host.sh <app_folder> [...]   e.g. tomcat_7.0 jetty_9.4.51
# Output: rerun_host/output-native/<name>_native.txt, rerun_host/output-syscalls/<name>_syscalls.txt
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
DATASETS="${DATASETS:-/home/user/Prototype/Final_results_echotrace}"
JAVA8=/usr/lib/jvm/java-8-openjdk-amd64/bin/java
OUT="$HERE/rerun_host"
ME="$(id -un)"
mkdir -p "$OUT/output-native" "$OUT/output-syscalls" "$OUT/logs" "$OUT/work"

for app in "$@"; do
  name="${app%%_*}"
  jars="$DATASETS/$app/Dataset/JARFILES_$app"
  libs="$DATASETS/$app/Dataset/LIBS_$app"
  work="$OUT/work/$app"
  rm -rf "$work" && mkdir -p "$work/desktop" "$work/apr" "$work/output-native" "$work/output-syscalls"
  cp "$HERE"/run/*.py "$HERE"/run/*.sh "$work/"
  cp -r "$HERE/mrx_desktop/native" "$work/desktop/native"
  # tomcat-native lives at a fixed host path in SWAT4J's build_tc_map; only tomcat ships it
  tc=$(ls "$libs"/libtcnative-1.so* 2>/dev/null | head -1 || true)
  [ -n "$tc" ] && cp "$tc" "$work/apr/libtcnative-1.so.0"

  (
    sudo unshare -m bash -c "
      mount --bind '$work/desktop' /home/mrx/Desktop
      mount --bind '$work/apr' /usr/local/apr/lib
      sudo -u '$ME' env LANG=C.UTF-8 bash -c '
        set -e -o pipefail
        cd \"$work\"
        # build_map() launches this asynchronously and reads soname/ immediately; pre-generate to avoid the race
        sh generate_all_jni_names.sh /home/mrx/Desktop
        echo \"=== [1/2] bytecode analysis ===\"
        $JAVA8 -Xss64m -Xmx4g -cp \"$HERE/run/classes:$HERE/run/asm-8.0.jar:$jars/*\" \
          com.sspku.jtracer.bytecode_new.NewByteCodeTracer \"$jars/\" output-native/${name}_native.txt \
          | grep -v \"^DEBUG: classpath\"
        echo \"=== [2/2] binary analysis ===\"
        python3 -u binary_analyser.py \"$libs\" output-native/${name}_native.txt
      '
    " > "$OUT/logs/$app.log" 2>&1 || true
    cp "$work/output-native/${name}_native.txt" "$OUT/output-native/" 2>/dev/null || true
    cp "$work/output-syscalls/${name}_syscalls.txt" "$OUT/output-syscalls/" 2>/dev/null || true
    echo "[done] $app -> $(wc -l < "$OUT/output-syscalls/${name}_syscalls.txt" 2>/dev/null || echo FAILED) syscalls"
  ) &
done
wait
