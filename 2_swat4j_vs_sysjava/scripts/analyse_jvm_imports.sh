#!/bin/bash
# libjvm.so's own syscalls that its mapped start functions cannot reach.
#
# The java launcher (libjli) reaches libjvm only through dlsym (JNI_CreateJavaVM, ...), so the JVM's
# start-up code and its internal threads (GC, compiler, PerfMemory, ...) are not in libjvm's call
# graph. SysPart cannot analyse libjvm from those entry points either: it runs out of memory (40 GB).
# libjvm has no SYSCALL instruction of its own (objdump), so every syscall it makes goes through a
# function it imports. This runs SysPart on each library libjvm imports from (DT_NEEDED: libc,
# libpthread, libdl, libm, ld-linux), starting only from the functions libjvm imports from it. Same
# method as the Elastic ML component (Final_results_JDK8/_ml_imports_recovery).
# Seen at run time and missed before: fchdir (PerfMemory::create_memory_region at start-up) and times
# (G1 GC-pause timing, TraceCPUTime).
#
# Output: jdk8_workspaces/<t>/extra_components/jvm_internal_imports/ (syscalls.txt, label.txt,
# README.md, start_<lib>.txt, syspart_<lib>/), read by merge_all_syscalls.py (STEP 4b).
# Usage: analyse_jvm_imports.sh <target>
#   env (another pipeline, e.g. EchoTrace_latest): JVMI_LIBS (symbolized libraries), JVMI_OUT (output folder),
#   JVMI_SYSPART (SysPart analysis/app)
#   JVMI_DLSYM_LIBS (latest set only, user decision 2026-11-11): a folder whose subfolders are the analysed
#     libraries (syscalls_output_<t>). Each of them that imports dlsym may call C-library functions it looks
#     up by name (e.g. JDK 21+ libnio: copy_file_range, statx), which no call graph shows. Its string
#     constants that name a function exported by one of the providers below, and that it does not import,
#     join that provider's start list (one SysPart run per provider). Recorded in dlsym_names.tsv.
set -u
T=$1
REPO=/home/user/Tutorial/EchoTrace
WS=$REPO/jdk8_workspaces/$T
L=${JVMI_LIBS:-$REPO/Final_results_JDK8/$T/Dataset_symbolized/LIBS_$T}
O=${JVMI_OUT:-$WS/extra_components/jvm_internal_imports}
DEPS=$L:$L/_container_deps$(for d in "$L"/JDK*_LIBS; do printf ':%s:%s/amd64:%s/amd64/server' "$d" "$d" "$d"; done)
J=$(find -L "$L" -name libjvm.so | head -1)
[ -n "$J" ] || { echo "no libjvm.so under $L" >&2; exit 1; }
rm -rf "${O:?}"; mkdir -p "$O"
nm -D --undefined-only "$J" | awk '{print $2}' | sed 's/@.*//' | sort -u > "$O/libjvm_imports.txt"
for n in $(readelf -d "$J" | sed -n 's/.*(NEEDED).*\[\(.*\)\]/\1/p'); do
  f=$(find -L "$L" -name "$n" | head -1)
  [ -n "$f" ] || { echo "$n: not in the dataset" | tee -a "$O/missing.txt"; continue; }
  nm -D --defined-only "$f" | awk '{print $3}' | sed 's/@.*//' | sort -u | comm -12 "$O/libjvm_imports.txt" - > "$O/start_$n.txt"
  [ -s "$O/start_$n.txt" ] || continue
  printf '%s\t%s\n' "$n" "$(realpath "$f")" >> "$O/providers.tsv"
done
if [ -n "${JVMI_DLSYM_LIBS:-}" ]; then
  : > "$O/dlsym_names.tsv"
  for d in "$JVMI_DLSYM_LIBS"/*/; do
    lib=$(find -L "$L" -name "$(basename "$d")" | head -1)
    [ -n "$lib" ] && nm -D --undefined-only "$lib" 2>/dev/null | grep -qw dlsym || continue
    strings -a -n 3 "$lib" | sort -u > "$O/.strings"
    nm -D --undefined-only "$lib" | awk '{print $2}' | sed 's/@.*//' | sort -u > "$O/.imports"
    while IFS=$'\t' read -r n f; do
      nm -D --defined-only "$f" | awk '$2 ~ /[TWi]/ {print $3}' | sed 's/@.*//' | sort -u | comm -12 "$O/.strings" - \
        | comm -23 - "$O/.imports" > "$O/.names"
      [ -s "$O/.names" ] || continue
      printf '%s\t%s\t%s\n' "$(basename "$d")" "$n" "$(tr '\n' ' ' < "$O/.names")" >> "$O/dlsym_names.tsv"
      sort -u "$O/start_$n.txt" "$O/.names" -o "$O/start_$n.txt"
    done < "$O/providers.tsv"
  done
  rm -f "$O/.strings" "$O/.imports" "$O/.names"
fi
cd "${JVMI_SYSPART:-$WS/SysPartCode/analysis/app}"
while IFS=$'\t' read -r n f; do
  out=$O/syspart_$n; mkdir -p "$out"
  ( ulimit -v $((24*1024*1024)); ulimit -s $((1024*1024))
    USER_LIBRARY_PATH="$DEPS" timeout -k 30 3600 nice -n 10 ./src/scripts/compute_syscalls.sh "$f" "$out" "$O/start_$n.txt" --log > "$out/run.log" 2>&1 )
  echo "$n exit=$? starts=$(wc -l < "$O/start_$n.txt") syscalls=$(wc -l < "$out/syscalls.txt" 2>/dev/null)" | tee -a "$O/runs.txt"
done < "$O/providers.tsv"
sort -u "$O"/syspart_*/syscalls.txt > "$O/syscalls.txt"
if [ -n "${JVMI_DLSYM_LIBS:-}" ]; then
  echo "libjvm internals via its imports, and C-library functions looked up with dlsym" > "$O/label.txt"
else
  echo "libjvm internals, via its libc/libpthread imports" > "$O/label.txt"
fi
cat > "$O/README.md" <<EOF
# libjvm internals, via the functions libjvm imports

The java launcher binds libjvm through dlsym, so libjvm's start-up code and internal threads are not
reachable from its mapped JNI start functions. SysPart ran on each library libjvm imports from
(DT_NEEDED), starting from only the functions libjvm imports from it (start_<lib>.txt).
Made by scripts/analyse_jvm_imports.sh $T. Per-library runs: runs.txt. Union: syscalls.txt.
With JVMI_DLSYM_LIBS: also the C-library functions that analysed libraries look up by name with dlsym
(dlsym_names.tsv: library, provider, names), added to the same start lists.
EOF
echo "union=$(wc -l < "$O/syscalls.txt")"
