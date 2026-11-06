#!/usr/bin/env python3
"""Classify every still-unmapped native (missing_natives.tsv) and write manual mappings
(../<target>/mapping/mapped_method_syscalls.txt, tag lines) and ../<target>/platform_extra.txt."""
import os
from collections import Counter
rows = [l.rstrip('\n').split('\t') for l in open('missing_natives.tsv')]
jvm = {(t, m): (s, d == 'True') for t, m, s, d, _ in (l.rstrip('\n').split('\t') for l in open('jdk_mapping_check.tsv'))}
LIBC = {'mlockall', 'getrlimit', 'geteuid', 'setrlimit', 'strerror'}
INTRINSIC = {'java.lang.Class.getSuperclass', 'java.lang.invoke.MethodHandle.invokeExact', 'jdk.internal.vm.Continuation.doYield'}
def cls(t, m):
    c, meth = m.rsplit('.', 1)
    if (t, m) in jvm and jvm[(t, m)][1]: return 'mapped', 'libjvm.so', jvm[(t, m)][0], 'JVM', 'JDK-internal native registered by the JVM itself (RegisterNatives / special native)'
    if c == 'org.elasticsearch.bootstrap.JNACLibrary' and meth in LIBC: return 'mapped', 'libc.so.6', meth, 'JNI', 'JNA direct mapping (Native.register) to libc'
    if m in INTRINSIC: return 'platform', '-', '-', '-', 'JVM intrinsic / signature-polymorphic: no native function'
    if 'Kernel32' in c or 'macos' in c.lower(): return 'platform', '-', '-', '-', 'Windows/macOS-only native'
    if '.uring.' in c: return 'not_found', '-', '-', '-', 'netty io_uring (shaded): library excluded, storm cannot load it (unshaded name)'
    if 'xerial.snappy' in c: return 'not_found', '-', '-', '-', 'shaded snappy: libsnappyjava exports unshaded Java_org_xerial_snappy_*, cannot link'
    if 'hawtjni.runtime.Callback' in c: return 'not_found', '-', '-', '-', 'hawtjni-runtime native library not shipped; not in any library on disk'
    if 'rocksdb' in c: return 'not_found', '-', '-', '-', 'not in the shipped rocksdb library (only in an older build) or exported only C++-mangled'
    if 'chronicle' in c or 'openhft.ticker' in c: return 'not_found', '-', '-', '-', 'Chronicle/OpenHFT native library not shipped (commercial/optional; Java fallback)'
    if c == 'com.kenai.jffi.Foreign': return 'not_found', '-', '-', '-', 'declared in jffi, absent from every jffi native build on disk (dead declaration)'
    if 'zstd' in c: return 'not_found', '-', '-', '-', 'declared in zstd-jni, absent from the shipped zstd-jni library'
    if 'commons.daemon' in c: return 'not_found', '-', '-', '-', 'implemented by the jsvc launcher (RegisterNatives), not shipped in the image'
    if 'quic' in c.lower(): return 'not_found', '-', '-', '-', 'netty quiche (shaded) symbol not exported'
    if (t, m) in jvm: return 'not_found', '-', '-', '-', 'JVM function not present in this libjvm'
    return 'not_found', '-', '-', '-', 'unexplained'
cnt = Counter()
with open('classification.tsv', 'w') as out:
    out.write('target\tmethod\tclass\tlibrary\tsymbol\ttag\treason\n')
    for t, m, _ in rows:
        k, lib, sym, tag, why = cls(t, m); cnt[(t, k)] += 1
        out.write(f"{t}\t{m}\t{k}\t{lib}\t{sym}\t{tag}\t{why}\n")
        if k == 'mapped':
            open(f'../{t}/mapping/mapped_method_syscalls.txt', 'a').write(f"notfound_search/{lib}:{m} -> {sym} [{tag}]\n")
        if k == 'platform':
            open(f'../{t}/platform_extra.txt', 'a').write(m + '\n')
for t in sorted({r[0] for r in rows}):
    print(t, {k: cnt[(t, k)] for k in ('mapped', 'platform', 'not_found') if cnt[(t, k)]})
