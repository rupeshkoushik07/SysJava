#!/usr/bin/env python3
"""Table V, SysJava (JNI-static) and SysJava (JNI-full) columns, from the shipped files of this artifact.
Same libraries, call graphs and libjvm imports as swat4j_binding.py; only the start functions differ:
  JNI-static: targets of [JNI] mappings (Java_* symbols: short, overloaded, escaped; incl. manual mappings of
              supplied libraries)
  JNI-full:   + [JNI_DYNAMIC] [REGISTERED] (RegisterNatives tables), [JVM] (JDK class tables to JVM_*), [NETTY]
  neither:    JNA, JNR-FFI, FFM, [DIRECT_LIBC_BRIDGE], [SIGAR_LIST_BRIDGE]
Methods: Java natives with at least one such target in an analysed library. libjvm's imports (the JVM itself)
are counted in every column. OrientDB's supplied libjffi-1.2.so: all 38 of its start functions are [JNI] mappings,
so both columns take its whole syscall list.
Usage: python3 jni_columns.py   -> results/jni_columns.tsv (+ table printed)"""
import collections, csv, glob, os, re
from swat4j_binding import Graph, names, RES, ART, IMAGES, H   # shared helpers (same folder)

STATIC = {"JNI"}
FULL = STATIC | {"JNI_DYNAMIC", "REGISTERED", "JVM", "NETTY", "NETTY_FUZZY"}
rows = []
for img_short in IMAGES:
    img = f"{img_short}-jdk8-buster"
    b, o = f"{RES}/{img}/Binary_Analysis", f"{RES}/{img}/Bytecode_Analysis/outputs_{img}"
    tgt = collections.defaultdict(set)                  # (library file name, symbol) -> {(native, tag)}
    for f in (f"{o}/mapped_method_syscalls.txt", f"{o}/manual_mapped_method_syscalls.txt"):
        for l in open(f, errors="replace") if os.path.exists(f) else []:
            m = re.match(r"(\S+?):(\S+) -> (\S+) \[([A-Z_]+)\]", l)
            if m and "NOT_FOUND" not in l:
                tgt[(os.path.basename(m.group(1)), m.group(3))].add((m.group(2), m.group(4)))
    imports = names(f"{b}/extra_components/jvm_internal_imports/syscalls.txt")
    graphs = {}
    out = []
    for tags in (STATIC, FULL):
        sysc, meth = set(imports), set()
        for d in sorted(glob.glob(f"{b}/syscalls_output_{img}/*/callgraph.json.gz")):
            d = os.path.dirname(d); lib = os.path.basename(d)
            sst = {s for s in names(f"{d}/startfuncs_resolved.txt") if any(t in tags for _, t in tgt.get((lib, s), ()))}
            if not sst:
                continue
            if d not in graphs:
                graphs[d] = Graph(d)
            sysc |= graphs[d].reach(sst)
            meth |= {n for s in sst for n, t in tgt[(lib, s)] if t in tags}
        if img_short.startswith("orientdb"):
            sysc |= names(f"{ART}/2_swat4j_vs_sysjava/manual_mapping/{img}/syspart_libjffi-1.2.so/syscalls.txt")
            meth |= {n for (lib, s), v in tgt.items() if lib == "libjffi-1.2.so" for n, t in v if t in tags}
        out.append((meth, sysc))
    (ms, ss), (mf, sf) = out
    rows.append([img, len(ms), len(ss), len(mf), len(sf), " ".join(sorted(sf - ss))])
    print(f"{img:34s} JNI-static {len(ms):5d} / {len(ss):3d}   JNI-full {len(mf):5d} / {len(sf):3d}", flush=True)
with open(f"{H}/results/jni_columns.tsv", "w", newline="") as f:
    w = csv.writer(f, delimiter="\t", lineterminator="\n")
    w.writerow(["image", "jni_static_methods", "jni_static_syscalls", "jni_full_methods", "jni_full_syscalls",
                "full_minus_static"])
    w.writerows(rows)
