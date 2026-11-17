#!/usr/bin/env python3
"""Table V, SysJava (JNI-static), SysJava (JNI-full) and SysJava binding columns, from the shipped files of this
artifact, on Table II's categories. Same libraries, call graphs and libjvm imports as swat4j_binding.py.
Category of a native = its first mapper tag, read as Table II's generator reads it
(sysjava_results/<img>/.../mapped_method_syscalls.txt, then manual_mapping/<img>/mapping/mapped_method_syscalls.txt):
  JNI-static  = Table II Sym. lookup: JNI (Java_* names), JVM (JDK class tables), SIGAR_LIST_BRIDGE
  JNI-full    = Table II JNI bound: + JNI_DYNAMIC, REGISTERED (RegisterNatives tables), NETTY  (Exp. reg.)
  binding     = JNI-full + bound JNA + bound JNR-FFI (library and function known, applicable on Linux)
JNA direct-mapped natives are counted under JNA only. Start functions: every target of the arm's natives in an
analysed library; binding adds the bound JNA functions and JRuby's JNR-FFI libc functions (inputs/jruby_jnr).
libjvm's imports (the JVM itself) in every arm. Tomcat's 2 jsvc natives are registered in the jsvc executable:
counted as methods, no library to walk.
Usage: python3 jni_columns.py   -> results/jni_columns.tsv (+ checks printed)"""
import collections, csv, glob, os, re
from swat4j_binding import Graph, names, RES, ART, IMAGES, H, PAPER_BINDING

STATIC = {"JNI", "JVM", "DIRECT_LIBC_BRIDGE", "SIGAR_LIST_BRIDGE"}
FULL = STATIC | {"JNI_DYNAMIC", "REGISTERED", "NETTY", "NETTY_FUZZY"}
MAN = f"{ART}/2_swat4j_vs_sysjava/manual_mapping"
WIN = {"kernel32", "msvcrt", "winmm"}
OTHER_FN = {"kevent", "kqueue", "sandbox_init", "sandbox_free_error", "priv_set"}
OTHER_CLASS = ("Darwin", "Windows", "Win32", "Kernel32", "WinLibC", "Solaris", "FreeBSD", "Bsd", "MacLibrary")
LINE = re.compile(r"^(?:\S+?:)?([\w.$]+) -> \S+ \[(\w+)\]")
TGT = re.compile(r"(\S+?):(\S+) -> (\S+) \[([A-Z_]+)\]")


def jside(s):
    m = re.match(r"<([^:]+): \S+ ([^(]+)\(", s)
    return f"{m.group(1)}.{m.group(2)}" if m else s


rows = []
for img_short, paper in zip(IMAGES, PAPER_BINDING):
    img = f"{img_short}-jdk8-buster"
    b, o = f"{RES}/{img}/Binary_Analysis", f"{RES}/{img}/Bytecode_Analysis/outputs_{img}"
    mapped, manual = f"{o}/mapped_method_syscalls.txt", f"{MAN}/{img}/mapping/mapped_method_syscalls.txt"
    cat, tgt = {}, collections.defaultdict(set)
    for f in (mapped, manual):
        for l in open(f, errors="replace") if os.path.exists(f) else []:
            m = LINE.match(l.strip())
            if m and (f == mapped or m.group(2) != "NOT_FOUND"):
                cat.setdefault(m.group(1), m.group(2))
    for f in (mapped, f"{o}/manual_mapped_method_syscalls.txt", manual):
        for l in open(f, errors="replace") if os.path.exists(f) else []:
            m = TGT.match(l)
            if m and "NOT_FOUND" not in l:
                tgt[(os.path.basename(m.group(1)), m.group(3))].add(m.group(2))
    hits = []
    if os.path.exists(f"{o}/jna_hits.txt"):
        hits = [[x.strip() for x in l.rstrip("\n").split(" | ")] for l in open(f"{o}/jna_hits.txt", errors="replace")]
        hits = [h for h in hits if len(h) >= 4]
    for h in hits:                                      # JNA direct mappings: JNA, not JNI
        if h[0] == "directmap":
            cat.pop(jside(h[1]), None)
    ovr = {}
    ops = [f"{MAN}/{img}/binding_overrides.tsv"]
    if img_short.startswith("jruby"):                   # as Table II: JRuby 9.4.2.0 uses the 10.1.0.0 classification
        ops.append(f"{ART}/1_latest_containers/manual_mapping/jruby_10.1.0.0/binding_overrides.tsv")
    for op in ops:
        if os.path.exists(op):
            for l in open(op):
                g = l.rstrip("\n").split("\t"); ovr.setdefault(tuple(g[:4]), g[4])

    def bound(h):
        ok = (h[2] not in ("<?>", "") and h[3] not in ("<?>", "")) or ovr.get(tuple(h[:4])) == "mapped"
        other = ({x.lower() for x in h[2].split("|")} & WIN) or h[3] in OTHER_FN or \
            any(k in h[1].split("(")[0] for k in OTHER_CLASS)
        return ok and not other

    imports = names(f"{b}/extra_components/jvm_internal_imports/syscalls.txt")
    graphs, res = {}, {}
    for arm, tags in (("static", STATIC), ("full", FULL)):
        natives = {n for n, c in cat.items() if c in tags}
        sysc = set(imports)
        for d in sorted(glob.glob(f"{b}/syscalls_output_{img}/*/callgraph.json.gz")):
            d = os.path.dirname(d); lib = os.path.basename(d)
            sst = {s for s in names(f"{d}/startfuncs_resolved.txt") if tgt.get((lib, s), set()) & natives}
            if sst:
                graphs.setdefault(d, None)
                if graphs[d] is None:
                    graphs[d] = Graph(d)
                sysc |= graphs[d].reach(sst)
        if img_short.startswith("orientdb"):            # supplied libjffi-1.2.so: all 38 starts are [JNI] mappings
            sysc |= names(f"{MAN}/{img}/syspart_libjffi-1.2.so/syscalls.txt")
        res[arm] = (natives, sysc)
    jna_rows = [h for h in hits if h[0] in ("directmap", "iface", "dyn") and bound(h)]
    jnr_rows = [h for h in hits if h[0] == "jnr-ffi" and bound(h)]
    bind = set(res["full"][1])
    for sd in sorted(glob.glob(f"{b}/jna_ffi_analysis/syscalls/*/")):
        sd = sd.rstrip("/")
        sst = names(f"{sd}/startfuncs_resolved.txt") & {h[3] for h in jna_rows}
        if sst:
            bind |= Graph(sd).reach(sst)
    if jnr_rows:
        bind |= names(f"{H}/inputs/jruby_jnr/syscalls.txt")
    (ns, ss), (nf, sf) = res["static"], res["full"]
    nb = len(nf) + len(jna_rows) + len(jnr_rows)
    nested = ss <= sf <= bind
    rows.append([img, len(ns), len(ss), len(nf), len(sf), len(jna_rows), len(jnr_rows), nb, len(bind), paper, nested])
    print(f"{img:34s} static {len(ns):5d} + exp {len(nf)-len(ns):4d} = full {len(nf):5d}; + JNA {len(jna_rows)} + JNR-FFI "
          f"{len(jnr_rows)} = binding {nb:5d}; syscalls {len(ss)} <= {len(sf)} <= {len(bind)} (paper {paper}) nested={nested}",
          flush=True)
with open(f"{H}/results/jni_columns.tsv", "w", newline="") as f:
    w = csv.writer(f, delimiter="\t", lineterminator="\n")
    w.writerow(["image", "jni_static_methods", "jni_static_syscalls", "jni_full_methods", "jni_full_syscalls",
                "jna_bound", "jnr_ffi_bound", "binding_methods", "binding_syscalls", "paper_binding_syscalls", "nested"])
    w.writerows(rows)
