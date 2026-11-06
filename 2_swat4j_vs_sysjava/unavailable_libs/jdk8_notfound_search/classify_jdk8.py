#!/usr/bin/env python3
"""Classify the Not Found natives of the JDK 8 set (Final_results_JDK8/<t>-jdk8-buster) that the
mapper run on the supplied libraries (../<t>/mapping/) did not resolve. Same rules as
notfound_search/classify.py for the latest set; every mapped symbol is checked to be defined in
the library it is mapped to (nm on the symbolized library), otherwise the native stays not_found.

Writes, per target:
  ../<t>/mapping/mapped_method_syscalls.txt   appended rule lines  "<lib>:<method> -> <sym> [TAG]"
  ../<t>/platform_extra.txt                   other-OS natives and JVM intrinsics
and classification_jdk8.tsv here (target, method, class, library, symbol, tag, reason).

Usage: classify_jdk8.py
"""
import glob, os, re, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
UNAV = os.path.dirname(HERE)
RES = os.path.expanduser("~/Tutorial/EchoTrace/Final_results_JDK8")
TARGETS = ["zookeeper_3.4.14", "tomcat_7.0", "cassandra_3.0.29", "jetty_9.4.51", "storm_2.4.0", "orientdb_3.2.19",
           "elasticsearch_7.5.2", "solr_8.7.0", "groovy_4.0.0", "jruby_9.4.2.0"]
WS = os.path.expanduser("~/Tutorial/EchoTrace/jdk8_workspaces")
# JDK-internal natives the JVM binds itself (the previous runs' mapping of the same methods)
JVM_RULES = {"sun.misc.Unsafe.registerNatives": "JVM_RegisterUnsafeMethods",
             "java.lang.invoke.MethodHandleNatives.registerNatives": "JVM_RegisterMethodHandleMethods",
             "jdk.jfr.internal.JVM.registerNatives": "jfr_register_natives",
             "jdk.jfr.internal.JVM.getClassId": "jfr_class_id",
             "sun.misc.Perf.createLong": "Perf_CreateLong",
             "sun.misc.Perf.attach": "Perf_Attach",
             "sun.misc.Perf.registerNatives": "JVM_RegisterPerfMethods",
             "sun.misc.Perf.detach": "Perf_Detach",
             # JDK 8 Class.registerNatives (libjava Class.c) binds getSuperclass to the JNI function GetSuperclass
             "java.lang.Class.getSuperclass": "jni_GetSuperclass"}
# netty 4.0 epoll registers this one under a netty_channel_ prefix (JNI_OnLoad RegisterNatives)
NETTY = {"io.netty.channel.unix.Socket.getPeerCredentials": "netty_channel_unix_socket_getPeerCredentials"}
LIBC = {"mlockall", "getrlimit", "geteuid", "setrlimit", "strerror"}   # ES JNACLibrary: JNA direct mapping
JSVC = {"org.apache.commons.daemon.support.DaemonLoader.shutdown": "shutdown",
        "org.apache.commons.daemon.support.DaemonLoader.failed": "failed"}   # jsvc java.c RegisterNatives
INTRINSIC = {"java.lang.invoke.MethodHandle.invokeExact"}
WINDOWS_ONLY = {"sun.font.FileFontStrike.initNative", "sun.font.FileFontStrike._getGlyphImageFromWindows"}
NOT_FOUND = [  # (pattern on the method, reason)
    (r"^jdk\.jfr\.internal\.JVM\.setCompressedIntegers$", "JFR native absent from this JDK 8u504 libjvm (no jfr_set_compressed_integers)"),
    (r"^com\.kenai\.jffi\.Foreign\.", "declared in jffi, absent from every jffi native build on disk (dead declaration)"),
    (r"^org\.fusesource\.hawtjni\.runtime\.Callback\.", "hawtjni callback natives exist only where a project compiles hawtjni-callback.c; the image's jansi/jline libjansi does not (dead declaration)"),
    (r"^org\.fusesource\.jansi\.internal\.CLibrary\.ttyslot$", "not exported by the image's own jansi 2.4.0 native library (dead declaration)"),
    (r"^org\.apache\.tomcat\.jni\.SSL\.(generateRSATempKey|loadDSATempKey)$", "removed from tcnative 1.2; absent from the image's libtcnative-1.so.0.2.28"),
    (r"^org\.rocksdb\.EnvOptions\.(setUseOsBuffer|useOsBuffer)$", "absent from the image's rocksdb JNI library (removed in RocksDB)"),
    (r"^org\.apache\.hadoop\.io\.erasurecode\.", "Hadoop erasure-coding natives exist only in an ISA-L build; the Apache 3.2.0 release libhadoop has none"),
    (r"^org\.apache\.hadoop\.(io\.nativeio\.NativeIO\$POSIX\.getUIDforFDOwnerforOwner|net\.unix\.DomainSocket\.write0)$", "declared in Hadoop's Java code only; no Hadoop C source or libhadoop build implements it (dead declaration)"),
    (r"^org\.apache\.hadoop\.", "not exported by the Hadoop 3.2.0 release libhadoop (version-specific)"),
]


def defined(lib, sym):
    out = subprocess.run(["nm", lib], capture_output=True, text=True).stdout + \
        subprocess.run(["nm", "-D", "--defined-only", lib], capture_output=True, text=True).stdout
    return any(l.split()[-1] == sym and l.split()[-2] in "TtWwi" for l in out.splitlines() if len(l.split()) >= 2)


rows = []
for t0 in TARGETS:
    t = t0 + "-jdk8-buster"
    d = os.path.join(UNAV, t)
    os.makedirs(os.path.join(d, "mapping"), exist_ok=True)
    # the newest mapping: the workspace's (current run) when it is newer than the published one
    cur = max(glob.glob(f"{RES}/{t}/Bytecode_Analysis/outputs_*/mapped_method_syscalls.txt") +
              glob.glob(f"{WS}/{t}/outputs_{t}/mapped_method_syscalls.txt"), key=os.path.getmtime)
    missing = sorted({l.split(":")[0] for l in open(cur, errors="replace") if "NOT_FOUND_IN_LIBS" in l} |
                     {l.split(" -> ")[0].split(":")[-1] for l in open(cur, errors="replace") if " -> <unresolved> " in l})
    mp = os.path.join(d, "mapping", "mapped_method_syscalls.txt")
    supplied = set()
    if os.path.exists(mp):
        supplied = {m.group(1) for l in open(mp) if (m := re.match(r"^(?:\S+?:)?([\w.$]+) -> \S+ \[\w+\]", l.strip()))}
    libs = f"{RES}/{t}/Dataset_symbolized/LIBS_{t}"
    jvm = glob.glob(f"{libs}/libjvm.so")[0]
    libc = (glob.glob(f"{libs}/libc.so.6") + glob.glob(f"{libs}/libc-2.*.so"))[0]
    new, platform = [], []
    for m in missing:
        cls, meth = m.rsplit(".", 1)
        if m in supplied:
            rows.append((t, m, "mapped", "(supplied library)", "-", "-", "mapped by the pipeline's mapper on the supplied library")); continue
        lib = sym = tag = None
        if m in JVM_RULES:
            lib, sym, tag, why = jvm, JVM_RULES[m], "JVM", "JDK-internal native the JVM registers itself"
        elif cls == "org.elasticsearch.bootstrap.JNACLibrary" and meth in LIBC:
            lib, sym, tag, why = libc, meth, "JNI", "JNA direct mapping (Native.register) to libc"
        elif m in NETTY:
            lib, sym, tag, why = glob.glob(f"{libs}/libnetty-transport-native-epoll.so")[0], NETTY[m], "NETTY", "netty 4.0.44 epoll library, registered under a netty_channel_ prefix"
        elif cls.startswith("org.apache.hadoop.io.erasurecode") and os.path.exists(os.path.join(d, "hadoop-3.3.6/libhadoop.so")):
            lib, sym, tag, why = os.path.join(d, "hadoop-3.3.6/libhadoop.so"), "Java_" + m.replace("_", "_1").replace("$", "_00024").replace(".", "_"), "JNI", "Apache Hadoop 3.3.6 release libhadoop (ISA-L erasure-coding natives)"
        elif m == "org.fusesource.jansi.internal.CLibrary.ttyslot" and os.path.exists(os.path.join(d, "jline-2.14.6/libjansi.so")):
            lib, sym, tag, why = os.path.join(d, "jline-2.14.6/libjansi.so"), "Java_org_fusesource_jansi_internal_CLibrary_ttyslot", "JNI", "jansi 1.x native library bundled in the image's jline 2.14.6 jar"
        elif m in JSVC:
            lib, sym, tag, why = os.path.join(d, "jsvc"), JSVC[m], "REGISTERED", "registered by jsvc (commons-daemon 1.2.4 built from the image's source)"
        if lib:
            if defined(lib, sym):
                new.append(f"{lib}:{m} -> {sym} [{tag}]")
                rows.append((t, m, "mapped", os.path.basename(lib), sym, tag, why)); continue
            why = f"{sym} not defined in {os.path.basename(lib)}"
            rows.append((t, m, "not_found", "-", "-", "-", why)); continue
        if m in INTRINSIC or m in WINDOWS_ONLY or "Kernel32" in cls or "Windows" in cls or "macos" in cls.lower():
            platform.append(m)
            rows.append((t, m, "platform", "-", "-", "-", "JVM intrinsic" if m in INTRINSIC else "Windows/macOS-only native")); continue
        why = next((r for p, r in NOT_FOUND if re.search(p, m)), "unexplained")
        rows.append((t, m, "not_found", "-", "-", "-", why))
    if new:
        with open(mp, "a") as f:
            f.write("\n".join(new) + "\n")
    with open(os.path.join(d, "platform_extra.txt"), "w") as f:
        f.write("".join(p + "\n" for p in platform))
    c = {k: sum(r[0] == t and r[2] == k for r in rows) for k in ("mapped", "platform", "not_found")}
    print(t, "missing", len(missing), c)

with open(os.path.join(HERE, "classification_jdk8.tsv"), "w") as f:
    f.write("target\tmethod\tclass\tlibrary\tsymbol\ttag\treason\n")
    for r in rows:
        f.write("\t".join(r) + "\n")
