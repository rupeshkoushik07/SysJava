#!/usr/bin/env python3
"""Not Found natives of the RTA rerun (workspaces_rta/<t>, detector 89bf135) that the published manual
mappings (../<t>/mapping, ../<t>/platform_extra.txt, classification.tsv) do not already cover.

Writes, per target, ../<t>/mapping_rta/mapped_method_syscalls.txt = the published manual mappings + the
new rule lines, and ../<t>/platform_extra_rta.txt = published platform list + new platform natives.
The published mapping/ and platform_extra.txt stay untouched (they belong to the published table).
Every mapped symbol is checked to be defined in its library (nm, symbol table).
Output here: classification_rta.tsv (target, method, class, library, symbol, tag, reason).

Usage: classify_rta.py
"""
import csv, glob, os, re, shutil, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
UNAV = os.path.dirname(HERE)
E = os.path.dirname(UNAV)
WS = f"{E}/workspaces_rta"
T = ["cassandra_5.0.8", "zookeeper_3.9.5", "tomcat_11.0.22", "solr_10.0.0", "groovy_5.0.6", "orientdb_3.2.53",
     "jetty_12.1.10", "elasticsearch_7.1.0", "storm_2.8.8", "jruby_10.1.0.0"]
# JDK-internal natives the JVM binds itself (registerNatives -> JVM_Register*, as in classify.py)
JVM = {"jdk.internal.misc.Unsafe.registerNatives": "JVM_RegisterJDKInternalMiscUnsafeMethods",
       "jdk.internal.misc.ScopedMemoryAccess.registerNatives": "JVM_RegisterJDKInternalMiscScopedMemoryAccessMethods",
       "java.lang.invoke.MethodHandleNatives.registerNatives": "JVM_RegisterMethodHandleMethods",
       "jdk.internal.perf.Perf.registerNatives": "JVM_RegisterPerfMethods",
       "jdk.internal.vm.vector.VectorSupport.registerNatives": "JVM_RegisterVectorSupportMethods",
       "jdk.jfr.internal.JVM.registerNatives": "jfr_register_natives",
       "jdk.internal.misc.VM.getNanoTimeAdjustment": "JVM_GetNanoTimeAdjustment"}
PLATFORM = {"java.lang.invoke.MethodHandle.invokeExact": "signature-polymorphic JVM intrinsic: no native function",
            "sun.font.FileFontStrike.initNative": "Windows-only font native (absent from Linux libfontmanager)"}
DEAD = {"sun.java2d.loops.TransformBlit.Transform":
        "declared native in TransformBlit.java; OpenJDK has no C implementation (every loop is a Java subclass that overrides it)"}
FALLBACK = "openjdk-25.0.3-fallbackLinker/libfallbackLinker.so"
ROCKS518 = "rocksdbjni-5.18.4/librocksdbjni-linux64.so"   # storm: natives its own rocksdb 10.10.1.1 library lacks
# natives with no implementation in any library or source (user decision 2026-11-07: counted as Dead)
DEAD_PATTERNS = [(r"^com\.kenai\.jffi\.Foreign\.", "declared in jffi Foreign.java since 2011; never implemented in C"),
                 (r"^com\.github\.luben\.zstd\.Zstd\.generateSequences$", "declared in zstd-jni Zstd.java; jni_zstd.c has no implementation"),
                 (r"^software\.chronicle\.enterprise\.internals\.impl\.NativeAffinity\.rdtsc0$", "declared in affinity 3.23.3; OpenHFT C source has no implementation"),
                 (r"^sun\.java2d\.loops\.TransformBlit\.Transform$", "declared native in TransformBlit.java; no C implementation in OpenJDK (Java subclasses override it)"),
                 (r"^org\.fusesource\.hawtjni\.runtime\.Callback\.", "hawtjni callback natives: no library in the image (or anywhere on disk) compiles hawtjni-callback.c"),
                 (r"^org\.rocksdb\.(LiveFileMetaData\.newLiveFileMetaDataHandle|RocksEnv\.disposeInternalJni)$", "declared in rocksdbjni 10.10.1.1; no rocksdb release (5.18.4 .. 11.8.1) implements it"),
                 (r"^jdk\.jfr\.internal\.JVM\.setCompressedIntegers$", "not in this libjvm's JFR registration table")]
LINE = re.compile(r"^(?:\S+?:)?([\w.$]+) -> \S+ \[(\w+)\]")


def defined(lib, sym):
    out = subprocess.run(["nm", lib], capture_output=True, text=True).stdout + \
        subprocess.run(["nm", "-D", "--defined-only", lib], capture_output=True, text=True).stdout
    return any(len(x.split()) >= 2 and x.split()[-1] == sym and x.split()[-2] in "TtWwi" for x in out.splitlines())


def jni(m):
    return "Java_" + m.replace("_", "_1").replace("$", "_00024").replace(".", "_")


cls = {(r["target"], r["method"]): r for r in csv.DictReader(open(f"{HERE}/classification.tsv"), delimiter="\t")}
rows = []
for t in T:
    res = glob.glob(f"{E}/Final_results_latest_versions_clinit/{t}") or glob.glob(f"{E}/Final_results_latest_versions/{t}")
    L = glob.glob(f"{res[0]}/Dataset_symbolized/LIBS_{t}")[0]
    nf = set()
    for l in open(f"{WS}/{t}/outputs_{t}/mapped_method_syscalls.txt", errors="replace"):
        l = l.strip()
        if "NOT_FOUND_IN_LIBS" in l:
            nf.add(l.split(":")[0].split(" ")[0])
        elif " -> <unresolved> " in l:
            nf.add(l.split(" -> ")[0].split(":")[-1])
    d = f"{UNAV}/{t}"
    os.makedirs(f"{d}/mapping_rta", exist_ok=True)
    pub = f"{d}/mapping/mapped_method_syscalls.txt"
    lines = open(pub).read().splitlines() if os.path.exists(pub) else []
    covered = {m.group(1) for x in lines if (m := LINE.match(x.strip())) and not m.group(2).startswith("NOT_FOUND")}
    pe = open(f"{d}/platform_extra.txt").read().split() if os.path.exists(f"{d}/platform_extra.txt") else []
    new_lines, new_pe, new_dead = [], [], []
    for m in sorted(nf):
        if m in covered or m in pe:
            continue
        dead = next((r for p_, r in DEAD_PATTERNS if re.search(p_, m)), None)
        if dead:
            new_pe.append(m); new_dead.append(m); rows.append((t, m, "dead", "-", "-", "-", dead)); continue
        old = cls.get((t, m))
        lib = sym = tag = why = None
        if t == "storm_2.8.8" and re.match(r"^org\.rocksdb\.(DB)?Options\.(set)?[fF]ailIfOptionsFileError$", m) and os.path.exists(f"{d}/{ROCKS518}"):
            lib, sym, tag, why = f"{d}/{ROCKS518}", jni(m), "JNI", "rocksdb 5.18.4 library (storm 2.4.0's rocksdbjni jar); storm 2.8.8's own library lacks it"
            pre = ROCKS518
        elif old and old["class"] == "not_found":
            rows.append((t, m, "not_found", "-", "-", "-", old["reason"])); continue
        elif m in JVM:
            lib, sym, tag, why = glob.glob(f"{L}/**/libjvm.so", recursive=True)[0], JVM[m], "JVM", "JDK-internal native the JVM registers itself"
            pre = f"LIBS_{t}/" + os.path.relpath(lib, L)
        elif m.startswith("jdk.internal.foreign.abi.fallback.LibFallback.") and os.path.exists(f"{d}/{FALLBACK}"):
            lib, sym, tag, why = f"{d}/{FALLBACK}", jni(m), "JNI", "OpenJDK 25.0.3 libfallbackLinker built from source (the image's JDK ships none)"
            pre = FALLBACK
        elif m.startswith("java.nio.MappedMemoryUtils."):
            lib = glob.glob(f"{L}/libnio.so")[0]
            sym, tag, why = "MappedMemoryUtils_" + m.rsplit(".", 1)[1], "REGISTERED", "registered by MappedMemoryUtils.registerNatives in the image's libnio"
            pre = f"LIBS_{t}/libnio.so"
        if lib:
            if defined(lib, sym):
                new_lines.append(f"{pre}:{m} -> {sym} [{tag}]")
                rows.append((t, m, "mapped", os.path.basename(lib), sym, tag, why)); continue
            rows.append((t, m, "not_found", "-", "-", "-", f"{sym} not defined in {os.path.basename(lib)}")); continue
        if m in PLATFORM:
            new_pe.append(m); rows.append((t, m, "platform", "-", "-", "-", PLATFORM[m])); continue
        rows.append((t, m, "not_found", "-", "-", "-", DEAD.get(m, "unexplained")))
    with open(f"{d}/mapping_rta/mapped_method_syscalls.txt", "w") as f:
        f.write("\n".join(lines + new_lines) + "\n")
    with open(f"{d}/platform_extra_rta.txt", "w") as f:   # platform + intrinsic + dead (table row "Platform / Intrinsic / Dead")
        f.write("".join(x + "\n" for x in pe + new_pe))
    with open(f"{d}/dead_rta.txt", "w") as f:
        f.write("".join(x + "\n" for x in new_dead))
    c = {k: sum(r[0] == t and r[2] == k for r in rows) for k in ("mapped", "platform", "dead", "not_found")}
    print(t, "pipeline Not Found", len(nf), "new rule lines", len(new_lines), c)

with open(f"{HERE}/classification_rta.tsv", "w") as f:
    f.write("target\tmethod\tclass\tlibrary\tsymbol\ttag\treason\n")
    for r in rows:
        f.write("\t".join(r) + "\n")
