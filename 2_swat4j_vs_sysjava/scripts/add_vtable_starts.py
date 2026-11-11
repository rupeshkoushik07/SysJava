#!/usr/bin/env python3
"""Add the functions a C++ library's vtables point to as stage-7 start functions.

SysPart resolves a virtual call to the functions whose address is taken somewhere in the library. When
a class's constructor is inlined and its vtable is only reached through a GOT entry (e.g. RocksDB's
PosixEnv), SysPart never sees that vtable's functions as address-taken, so a virtual call such as
WritableFile::Allocate -> PosixWritableFile::Allocate -> fallocate drops out of the call graph.
Every function listed in a vtable (relocations inside a _ZTV* object) can be the target of a virtual
call, so it is added to the library's start list.

libjvm.so is left out on purpose: its 2,600 vtables cover most of HotSpot, and SysPart already runs
out of memory on libjvm with all functions as starts. The JVM-internal syscalls it misses are covered
by scripts/analyse_jvm_imports.sh instead.

The start files are changed in place (like apply_manual_mappings.py), so each library is still
analysed once, from one start list. Rerunning is a no-op once the functions are in.

Usage: add_vtable_starts.py <target> [--repo DIR] [--outputs DIR --libs DIR]
  --outputs/--libs: start-file folder and symbolized-library folder of another pipeline (EchoTrace_latest)
Prints the start files whose set changed (the libraries stage 7 must analyse again) and writes
outputs_<t>/vtable_starts_added.tsv (start file, vtables, vtable functions, newly added).
"""
import argparse, bisect, glob, os, subprocess

ap = argparse.ArgumentParser()
ap.add_argument("target")
ap.add_argument("--repo", default=os.path.expanduser("~/Tutorial/EchoTrace"))
ap.add_argument("--outputs")
ap.add_argument("--libs")
a = ap.parse_args()
T = a.target
SLIBS = f"{a.repo}/Final_results_JDK8/{T}/Dataset_symbolized/LIBS_{T}"
OUT = f"{a.repo}/jdk8_workspaces/{T}/outputs_{T}"
if not os.path.isdir(OUT):                                 # a finished run keeps its outputs in Final_results_JDK8
    OUT = f"{a.repo}/Final_results_JDK8/{T}/Bytecode_Analysis/outputs_{T}"
SLIBS, OUT = a.libs or SLIBS, a.outputs or OUT
SKIP = {"libjvm.so"}


def run(*cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout.splitlines()


def vtable_functions(lib):
    """(number of vtables, names of the functions they point to)."""
    vt = []
    for l in run("nm", "-S", "--defined-only", lib):
        p = l.split()
        if len(p) == 4 and p[3].startswith("_ZTV"):
            vt.append((int(p[0], 16), int(p[0], 16) + int(p[1], 16)))
    if not vt:
        return 0, set()
    vt.sort()
    st = [v[0] for v in vt]
    names = {}
    for l in run("nm", "--defined-only", lib):
        p = l.split()
        if len(p) == 3 and p[1] in "Tt":
            names.setdefault(int(p[0], 16), p[2])
    out = set()
    for l in run("readelf", "-rW", lib):
        p = l.split()
        if len(p) < 4 or p[2] not in ("R_X86_64_64", "R_X86_64_RELATIVE"):
            continue
        off = int(p[0], 16)
        i = bisect.bisect_right(st, off) - 1
        if i < 0 or not (vt[i][0] <= off < vt[i][1]):
            continue
        val = int(p[3], 16)
        if val in names:
            out.add(names[val])
    return len(vt), out


rows = []
for f in sorted(glob.glob(f"{OUT}/**/*.so*.txt", recursive=True)):
    rel = os.path.relpath(f, OUT)[:-4]
    lib = os.path.join(SLIBS, rel)
    if os.path.basename(rel) in SKIP or not os.path.isfile(lib):
        continue
    n_vt, funcs = vtable_functions(lib)
    if not funcs:
        continue
    have = {l.strip() for l in open(f) if l.strip()}
    new = funcs - have
    if new:
        with open(f, "w") as fh:
            fh.write("\n".join(sorted(have | funcs)) + "\n")
        print(os.path.relpath(f, OUT))
    rows.append(f"{os.path.relpath(f, OUT)}\t{n_vt}\t{len(funcs)}\t{len(new)}")
with open(f"{OUT}/vtable_starts_added.tsv", "w") as fh:
    fh.write("start_file\tvtables\tvtable_functions\tnewly_added\n" + "".join(r + "\n" for r in rows))
