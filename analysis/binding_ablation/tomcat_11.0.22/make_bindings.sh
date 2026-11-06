#!/bin/bash
# Binding start lists and run targets for the Tomcat 11.0.22 ablation, from the
# latest-versions pipeline's results (read only).
#   JNI libraries: the functions the pipeline mapped native methods to (its own
#     per-library start list, <lib>.txt in Bytecode_Analysis/outputs_<img>).
#   FFM libraries (libssl, libcrypto): the downcallHandle symbols in ffi_hits.txt
#     ("caller | library | symbol | mechanism | jar"; upcall stubs, library "<?>",
#     left out) that the library defines (nm -D --defined-only).
# Writes bindings/<lib>.txt, bindings/ffm_not_in_openssl3.txt (downcall symbols
# neither library exports), a copy of ffi_hits.txt, and the targets_*.tsv lists
# run_ablation.sh (TARGETS=) and run_jdk_window.sh read.
#
# Usage: make_bindings.sh [out-dir]   (default: this directory)
set -euo pipefail
T="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${1:-$T}"
R=/home/user/Tutorial/EchoTrace_latest/Final_results_latest_versions/tomcat_11.0.22
O=$R/Bytecode_Analysis/outputs_tomcat_11.0.22
L=$R/Dataset_symbolized/LIBS_tomcat_11.0.22
B=$OUT/bindings
mkdir -p "$B"
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT

awk -F' [|] ' 'NF>=5 && $4=="downcallHandle" && $2!="<?>" {print $3}' "$O/ffi_hits.txt" \
    | sort -u > "$tmp/ffm"
for l in libssl.so.3 libcrypto.so.3; do
    nm -D --defined-only "$L/$l" | awk '{sub(/@.*/, "", $3); print $3}' | sort -u > "$tmp/def_$l"
    comm -12 "$tmp/ffm" "$tmp/def_$l" > "$B/$l.txt"
done
comm -23 "$tmp/ffm" <(sort -u "$tmp/def_libssl.so.3" "$tmp/def_libcrypto.so.3") \
    > "$B/ffm_not_in_openssl3.txt"
cp "$O/ffi_hits.txt" "$B/ffi_hits.txt"

sort -u "$O/libtcnative-2.so.0.0.14.txt" > "$B/libtcnative-2.so.0.0.14.txt"
for l in libjava.so libnet.so libzip.so; do sort -u "$O/JDK25_LIBS/$l.txt" > "$B/$l.txt"; done
sort -u "$O/JDK25_LIBS/server/libjvm.so.txt" > "$B/libjvm.so.txt"

# lib <TAB> library file <TAB> binding start list; T (not OUT) so the lists
# point at this directory's start lists.
row() { printf '%s\t%s\t%s\n' "$1" "$L/$2" "$T/bindings/$1.txt"; }
{ row libssl.so.3 libssl.so.3; row libtcnative-2.so.0.0.14 libtcnative-2.so.0.0.14
  row libcrypto.so.3 libcrypto.so.3; row libnet.so JDK25_LIBS/libnet.so
  row libzip.so JDK25_LIBS/libzip.so; row libjava.so JDK25_LIBS/libjava.so; } \
    > "$OUT/targets_small.tsv"
{ row libnet.so JDK25_LIBS/libnet.so; row libzip.so JDK25_LIBS/libzip.so
  row libjava.so JDK25_LIBS/libjava.so; } > "$OUT/targets_jdk3.tsv"
row libjvm.so JDK25_LIBS/server/libjvm.so > "$OUT/targets_libjvm.tsv"
wc -l "$B"/*.txt
