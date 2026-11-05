#!/bin/bash
# Run SWAT4J (facumolina HEAD, unmodified) on EchoTrace's container datasets inside
# an Ubuntu 18.04 + OpenJDK 8 image, the host environment SWAT4J hardcodes.
#
# Usage: run_swat4j.sh <app_folder> [<app_folder> ...]   e.g. tomcat_7.0 jetty_9.4.51
# Output: rerun/output-native/<swat_name>_native.txt, rerun/output-syscalls/<swat_name>_syscalls.txt
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
DATASETS="${DATASETS:-$HERE/../EchoTrace/Final_results_echotrace}"
IMAGE="swat4j-env:jdk8"
ASM_JAR="$HERE/run/asm-8.0.jar"

[ -f "$ASM_JAR" ] || cp /home/user/SWAT4J/asm-8.0.jar "$ASM_JAR"
mkdir -p "$HERE/rerun/output-native" "$HERE/rerun/output-syscalls" "$HERE/rerun/logs" "$HERE/rerun/work"

# Compile only the bytecode_new tracer (other packages need javaparser and are unused)
if [ ! -d "$HERE/run/classes" ]; then
  docker run --rm -u "$(id -u):$(id -g)" -v "$HERE/run:/swat" -w /swat "$IMAGE" \
    bash -c 'mkdir -p classes && javac -nowarn -encoding UTF-8 -cp asm-8.0.jar -d classes src/main/java/com/sspku/jtracer/bytecode_new/*.java'
fi

for app in "$@"; do
  name="${app%%_*}"   # tomcat_7.0 -> tomcat (SWAT4J's naming)
  jars="$DATASETS/$app/Dataset/JARFILES_$app"
  libs="$DATASETS/$app/Dataset/LIBS_$app"
  work="$HERE/rerun/work/$app"
  rm -rf "$work" && mkdir -p "$work/desktop" "$work/output-native" "$work/output-syscalls"
  cp "$HERE"/run/*.py "$HERE"/run/*.sh "$work/"
  cp -r "$HERE/mrx_desktop/native" "$work/desktop/native"

  (
    docker run --rm --name "swat4j_$app" -e LANG=C.UTF-8 \
      -v "$HERE/run/classes:/swat/classes:ro" -v "$ASM_JAR:/swat/asm.jar:ro" \
      -v "$jars:/data/jars:ro" -v "$libs:/data/libs:ro" \
      -v "$work:/work" -v "$work/desktop:/home/mrx/Desktop" \
      -w /work "$IMAGE" bash -c "
        set -e -o pipefail
        trap 'chown -R $(id -u):$(id -g) /work /home/mrx/Desktop' EXIT
        # tomcat-native lives at a fixed host path in SWAT4J's build_tc_map
        tc=\$(ls /data/libs/libtcnative-1.so* 2>/dev/null | head -1 || true)
        if [ -n \"\$tc\" ]; then mkdir -p /usr/local/apr/lib && cp \"\$tc\" /usr/local/apr/lib/libtcnative-1.so.0; fi
        # build_map() launches this asynchronously and reads soname/ immediately; pre-generate to avoid the race
        sh generate_all_jni_names.sh /home/mrx/Desktop
        echo '=== [1/2] bytecode analysis ==='
        java -Xss64m -Xmx4g -cp '/swat/classes:/swat/asm.jar:/data/jars/*' \
          com.sspku.jtracer.bytecode_new.NewByteCodeTracer /data/jars/ output-native/${name}_native.txt \
          | grep -v '^DEBUG: classpath'
        echo '=== [2/2] binary analysis ==='
        python3 -u binary_analyser.py /data/libs output-native/${name}_native.txt
      " > "$HERE/rerun/logs/$app.log" 2>&1
    cp "$work/output-native/${name}_native.txt" "$HERE/rerun/output-native/" 2>/dev/null || true
    cp "$work/output-syscalls/${name}_syscalls.txt" "$HERE/rerun/output-syscalls/" 2>/dev/null || true
    echo "[done] $app -> $(wc -l < "$HERE/rerun/output-syscalls/${name}_syscalls.txt" 2>/dev/null || echo FAILED) syscalls"
  ) &
done
wait
