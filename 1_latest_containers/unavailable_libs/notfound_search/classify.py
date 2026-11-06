#!/usr/bin/env python3
"""Classify every still-unmapped native (missing_natives.tsv) and write manual mappings
(../<target>/mapping/mapped_method_syscalls.txt, tag lines) and ../<target>/platform_extra.txt."""
import os
from collections import Counter
rows = [l.rstrip('\n').split('\t') for l in open('missing_natives.tsv')]
jvm = {(t, m): (s, d == 'True') for t, m, s, d, _ in (l.rstrip('\n').split('\t') for l in open('jdk_mapping_check.tsv'))}
LIBC = {'mlockall', 'getrlimit', 'geteuid', 'setrlimit', 'strerror'}
SNAPPY = [l.strip() for l in open('snappy_storm_symbols.txt')] if os.path.exists('snappy_storm_symbols.txt') else []
def jni(name): return name.replace('_', '_1').replace('$', '_00024').replace('.', '_')
OPENHFT = 'openhft-affinity-3.23.3/libCEInternals.so'
OPENHFT_DEAD = {'software.chronicle.enterprise.internals.impl.NativeAffinity.rdtsc0'}
INTRINSIC = {'java.lang.Class.getSuperclass', 'java.lang.invoke.MethodHandle.invokeExact', 'jdk.internal.vm.Continuation.doYield'}
def cls(t, m):
    c, meth = m.rsplit('.', 1)
    if (t, m) in jvm and jvm[(t, m)][1]: return 'mapped', 'libjvm.so', jvm[(t, m)][0], 'JVM', 'JDK-internal native registered by the JVM itself (RegisterNatives / special native)'
    if c == 'org.elasticsearch.bootstrap.JNACLibrary' and meth in LIBC: return 'mapped', 'libc.so.6', meth, 'JNI', 'JNA direct mapping (Native.register) to libc'
    if m in INTRINSIC: return 'platform', '-', '-', '-', 'JVM intrinsic / signature-polymorphic: no native function'
    if 'Kernel32' in c or 'macos' in c.lower(): return 'platform', '-', '-', '-', 'Windows/macOS-only native'
    if '.uring.' in c: return 'not_found', '-', '-', '-', 'netty io_uring (shaded): library excluded, storm cannot load it (unshaded name)'
    if 'xerial.snappy' in c and c.startswith('org.apache.storm.shade.'):
        syms = [x for x in SNAPPY if x == 'Java_' + jni(m[len('org.apache.storm.shade.'):]) or x.startswith('Java_' + jni(m[len('org.apache.storm.shade.'):]) + '__')]
        if syms: return 'mapped', 'LIBS_storm_2.8.8/libsnappyjava_storm-shaded-deps-2.8.8.so', syms, 'JNI', 'shaded alias of org.xerial.snappy native (same code in the shipped libsnappyjava, unshaded JNI name)'
    if 'xerial.snappy' in c: return 'not_found', '-', '-', '-', 'shaded snappy: libsnappyjava exports unshaded Java_org_xerial_snappy_*, cannot link'
    if 'hawtjni.runtime.Callback' in c: return 'not_found', '-', '-', '-', "hawtjni callback natives exist only where a project compiles hawtjni-callback.c; no library in the image does (dead declaration)"
    if m == 'org.rocksdb.WBWIRocksIterator.refresh0Jni':
        return 'mapped', 'LIBS_storm_2.8.8/librocksdbjni16624330668920755723.so', ['_Z46Java_org_rocksdb_WBWIRocksIterator_refresh0JniP7JNIEnv_P8_jobjectl'], 'JNI', 'implemented in the shipped rocksdb library, exported only C++-mangled'
    if 'rocksdb' in c: return 'not_found', '-', '-', '-', 'not in the shipped rocksdb library (only in an older build) or exported only C++-mangled'
    if m in OPENHFT_DEAD: return 'not_found', '-', '-', '-', 'declared in affinity-3.23.3.jar; OpenHFT Java-Thread-Affinity 3.23.3 C source has no implementation (dead declaration)'
    if ('chronicle' in c or 'openhft.ticker' in c) and os.path.exists(f'../{t}/{OPENHFT}'):
        return 'mapped', OPENHFT, 'Java_' + m.replace('_', '_1').replace('.', '_'), 'JNI', 'libCEInternals.so built from OpenHFT Java-Thread-Affinity 3.23.3 source (the image ships the jar only)'
    if 'chronicle' in c or 'openhft.ticker' in c: return 'not_found', '-', '-', '-', 'Chronicle/OpenHFT native library not shipped (commercial/optional; Java fallback)'
    if c == 'com.kenai.jffi.Foreign': return 'not_found', '-', '-', '-', 'declared in jffi Foreign.java since 2011; no C implementation anywhere in jffi git history (dead declaration)'
    if 'zstd' in c: return 'not_found', '-', '-', '-', 'declared in zstd-jni 1.5.7-2 Zstd.java; jni_zstd.c defines no Java_..._generateSequences (dead declaration)'
    if 'commons.daemon' in c: return 'not_found', '-', '-', '-', 'implemented by the jsvc launcher (RegisterNatives), not shipped in the image'
    if m.endswith('.quic.Quiche.quiche_enable_debug_logging'):
        return 'mapped', 'LIBS_storm_2.8.8/libnetty_quiche42_linux_x86_64-4.2.12.Final.so', ['netty_quiche_enable_debug_logging'], 'REGISTERED', 'shaded alias of the netty quiche registered native (as the pipeline maps the other Storm quiche natives)'
    if 'quic' in c.lower(): return 'not_found', '-', '-', '-', 'netty quiche (shaded) symbol not exported'
    if (t, m) in jvm: return 'not_found', '-', '-', '-', 'JVM function not present in this libjvm'
    return 'not_found', '-', '-', '-', 'unexplained'
def add_line(path, line):   # idempotent append: reruns do not duplicate lines
    if not (os.path.exists(path) and line in open(path).read().splitlines()):
        open(path, 'a').write(line + '\n')
cnt = Counter()
with open('classification.tsv', 'w') as out:
    out.write('target\tmethod\tclass\tlibrary\tsymbol\ttag\treason\n')
    for t, m, _ in rows:
        k, lib, sym, tag, why = cls(t, m); cnt[(t, k)] += 1
        out.write(f"{t}\t{m}\t{k}\t{lib}\t{','.join(sym) if isinstance(sym, list) else sym}\t{tag}\t{why}\n")
        if k == 'mapped':
            for sy in (sym if isinstance(sym, list) else [sym]):
                pre = lib if lib == OPENHFT or lib.startswith('LIBS_') else 'notfound_search/' + lib
                add_line(f'../{t}/mapping/mapped_method_syscalls.txt', f"{pre}:{m} -> {sy} [{tag}]")
        if k == 'platform':
            add_line(f'../{t}/platform_extra.txt', m)
for t in sorted({r[0] for r in rows}):
    print(t, {k: cnt[(t, k)] for k in ('mapped', 'platform', 'not_found') if cnt[(t, k)]})
