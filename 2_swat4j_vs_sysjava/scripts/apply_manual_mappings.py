#!/usr/bin/env python3
"""Fold the manual native mappings of a target into the pipeline's own stage-7 inputs, so that every
library is analysed once, from one start list (pipeline-mapped + manually mapped functions), and a
rerun of stage 7 rebuilds exactly the same call graphs.

Input:  <manual_dir>/<target>/mapping/mapped_method_syscalls.txt
        lines "<lib>:<method> -> <symbol> [TAG]"; <lib> is an absolute path, or a path relative to
        <manual_dir>/<target> for a supplied library. [NOT_FOUND] lines are ignored.
Output (in the target's workspace):
  - a supplied library is copied into the symbolized dataset under LIBS_<t>/_supplied/ (a
    version-suffixed name when two supplied libraries share a basename, e.g. two libhadoop.so);
  - its symbols are merged into outputs_<t>/<path-in-dataset>.txt, the start-function file stage 7
    reads; a library the pipeline already maps (libjvm, libc, netty) keeps its file and gains the
    manual symbols;
  - outputs_<t>/manual_mapped_method_syscalls.txt: the manual mappings, rewritten to dataset paths;
  - prints the start files whose set changed (the libraries stage 7 must analyse again).

Usage: apply_manual_mappings.py <target> [--manual-dir DIR] [--repo DIR]
"""
import argparse, glob, hashlib, os, re, shutil

ap = argparse.ArgumentParser()
ap.add_argument("target")
ap.add_argument("--manual-dir", default=os.path.expanduser("~/Tutorial/EchoTrace_latest/unavailable_libs"))
ap.add_argument("--repo", default=os.path.expanduser("~/Tutorial/EchoTrace"))
a = ap.parse_args()
T = a.target
MAN = os.path.join(a.manual_dir, T)
SLIBS = f"{a.repo}/Final_results_JDK8/{T}/Dataset_symbolized/LIBS_{T}"
OUT = f"{a.repo}/jdk8_workspaces/{T}/outputs_{T}"
if not os.path.isdir(OUT):                                 # a finished run keeps its outputs in Final_results_JDK8
    OUT = f"{a.repo}/Final_results_JDK8/{T}/Bytecode_Analysis/outputs_{T}"
LINE = re.compile(r"^(\S+?):([\w.$]+) -> (\S+) \[(\w+)\]")


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def start_file_for(lib):
    """The stage-7 start file for <lib>: the pipeline's own one when it already analyses the same
    library (same bytes), else a new one under _supplied/."""
    real = os.path.realpath(lib)
    if real.startswith(os.path.realpath(SLIBS) + "/"):
        h = sha(real)
        for f in glob.glob(f"{OUT}/**/{os.path.basename(lib)}.txt", recursive=True):
            cand = os.path.join(SLIBS, os.path.relpath(f, OUT)[:-4])
            if os.path.exists(cand) and sha(cand) == h:
                return f, cand
        return os.path.join(OUT, os.path.relpath(real, os.path.realpath(SLIBS)) + ".txt"), lib
    rel = os.path.relpath(real, MAN)                      # e.g. hadoop-3.3.6/libhadoop.so
    base = os.path.basename(rel)
    if os.path.dirname(rel):                              # versioned subfolder -> libhadoop-3.3.6.so
        stem, ext = base.split(".so", 1)
        base = f"{stem}-{os.path.dirname(rel).split('-')[-1]}.so{ext}"
    dst = os.path.join(SLIBS, "_supplied", base)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if not os.path.exists(dst) or sha(dst) != sha(real):
        shutil.copy2(real, dst)
    return os.path.join(OUT, "_supplied", base + ".txt"), dst


mp = os.path.join(MAN, "mapping", "mapped_method_syscalls.txt")
if not os.path.exists(mp):
    raise SystemExit(f"{T}: no manual mappings")
starts, lines = {}, []
for l in open(mp, errors="replace"):
    m = LINE.match(l.strip())
    if not m or m.group(4).startswith("NOT_FOUND"):
        continue
    lib, meth, sym, tag = m.groups()
    path = lib if lib.startswith("/") else os.path.join(MAN, lib)
    if not os.path.exists(path):
        print(f"{T}: missing library {path}, skipped {meth}")
        continue
    if ".so" not in os.path.basename(path):               # executables (jsvc): stage 7 reads only *.so start files
        continue
    sf, inset = start_file_for(path)
    starts.setdefault(sf, set()).add(sym)
    lines.append(f"LIBS_{T}/{os.path.relpath(inset, SLIBS)}:{meth} -> {sym} [{tag}]")

with open(os.path.join(OUT, "manual_mapped_method_syscalls.txt"), "w") as f:
    f.write("".join(sorted(set(x + "\n" for x in lines))))
for sf, syms in sorted(starts.items()):
    old = [x.strip() for x in open(sf)] if os.path.exists(sf) else []
    add = sorted(syms - set(old))
    if add:
        os.makedirs(os.path.dirname(sf), exist_ok=True)
        tmp = sf + ".tmp"
        with open(tmp, "w") as f:
            f.write("".join(x + "\n" for x in old + add if x))
        os.replace(tmp, sf)
    print(f"{'CHANGED' if add else 'same   '} {os.path.relpath(sf, OUT)}  pipeline={len(old)} manual={len(syms)} added={len(add)}")
