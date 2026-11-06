#!/usr/bin/env python3
"""Classify unresolved JNA/JNR/FFM bindings (library or symbol unknown) of each latest target and
write ../<target>/binding_overrides.tsv: detector, caller, lib, symbol, class, reason."""
import glob, os, re
R = '/home/user/Tutorial/EchoTrace_latest/Final_results_latest_versions'
U = '/home/user/Tutorial/EchoTrace_latest/unavailable_libs'
for d in sorted(glob.glob(R + '/*/Bytecode_Analysis/outputs_*')):
    t = d.split('/')[-3]
    rows = []
    for l in open(d + '/jna_hits.txt', errors='replace').readlines()[2:]:
        f = [x.strip() for x in l.split('|')]
        if len(f) < 4 or f[0] not in ('iface', 'dyn', 'ffi', 'jnr-ffi'):
            continue
        if f[2] not in ('<?>', '') and f[3] not in ('<?>', ''):
            continue
        c, lc = f[1], f[1].lower()
        if re.search(r'solaris|freebsd|osx|darwin|macos|win|kernel32|msvcrt', lc):
            k, why = 'platform', 'non-Linux binding'
        elif f[0] == 'ffi' and re.search(r'(\$(callback|cb|dh)|_cb)\b', c):
            k, why = 'platform', 'FFM upcall callback: native code calls Java, no native target'
        elif re.search(r'linux|unixsocket|rubybasicsocket\$libc', lc) and f[3] not in ('<?>', ''):
            k, why = 'mapped', 'libc binding (library name not propagated)'
        elif f[0] == 'dyn' and 'LinuxHelper' in c and 'sched_getcpu' in c:
            k, why = 'platform', 'call through the vsyscall/vDSO address, no shared library'
        else:
            k, why = 'not_found', 'library or symbol unknown'
        rows.append('\t'.join(f[:4] + [k, why]))
    if rows:
        os.makedirs(f'{U}/{t}', exist_ok=True)
        open(f'{U}/{t}/binding_overrides.tsv', 'w').write('\n'.join(rows) + '\n')
        from collections import Counter
        print(t, dict(Counter(r.split('\t')[4] for r in rows)))
        for r in rows:
            if r.split('\t')[4] == 'not_found': print('   NF:', r[:160])
