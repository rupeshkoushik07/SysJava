#!/usr/bin/env python3
"""
Per-library, per-mechanism entry-point ablation.

For every library SysPart analysed, the call graph is held fixed and the entry
points are split by the binding mechanism SysJava used to find them:

  JNI static           Java_* export found in the library        (tag JNI)
  RegisterNatives app  JNI_OnLoad RegisterNatives table in an app library
                                                                  (JNI_DYNAMIC, NETTY)
  RegisterNatives JVM  libjvm/libjava RegisterNatives tables      (REGISTERED)
  JVM_ entry           JVM_* function behind a JDK native         (JVM, JVM_BUILTIN)
  JNA                  JNA direct mapping / interface binding     (DIRECT_LIBC_BRIDGE, jna_*)
  FFM                  Panama downcallHandle (Linker)             (ffi_hits)
  manual bridge        hand-written list bridges                  (SIGAR_LIST_BRIDGE)

SWAT4J's entry points for a library are every symbol its mapping produced
(Java_XXX and JVM_XXX only) that the library defines. The file SWAT4J named is
ignored: copies of one library are often extracted twice (jar copy vs. the
temp copy loaded at runtime), and crediting by symbol keeps the comparison
conservative for SWAT4J. Reachable syscalls are computed twice:

  full     SysPart's model: indirect calls go to every address-taken function
           (identical to getsyscalls_lowmem.py; checked against syscalls.txt)
  direct   indirect edges dropped: only what the entry points reach through
           direct calls. Not sound, but it removes the address-taken blow-up,
           so it shows what each mechanism's entry points contribute themselves.

Writes, under --out:
  per_library.csv     one row per (app, lib, mode, arm): starts and syscalls
  mechanisms.csv      one row per (app, lib, mode, mechanism)
  missed.csv          syscalls SysJava reaches and SWAT4J's mapping does not,
                      with the mechanism(s) and a sample entry point that reach it
  check.csv           full-mode replay of SysJava's starts == syscalls.txt
  skipped.csv         SysPart library folders without a start list
"""
import argparse
import csv
import json
import os
import re
from array import array
from collections import Counter, OrderedDict, deque

TAG_MECH = {
    "JNI": "JNI static",
    "JNI_DYNAMIC": "RegisterNatives app",
    "NETTY": "RegisterNatives app",
    "REGISTERED": "RegisterNatives JVM",
    "JVM": "JVM_ entry",
    "JVM_BUILTIN": "JVM_ entry",
    "DIRECT_LIBC_BRIDGE": "JNA",
    "SIGAR_LIST_BRIDGE": "manual bridge",
}
MAPPED_TAGS = set(TAG_MECH)
REPORT_MECH = {"ffi_hits.txt": "FFM", "ffi_all_hits.txt": "FFM", "jna_hits.txt": "JNA",
               "jna_directmap_hits.txt": "JNA", "jna_iface_hits.txt": "JNA",
               "jnr_ffi_hits.txt": "JNR-FFI"}
MECH_ORDER = ["JNI static", "RegisterNatives app", "RegisterNatives JVM", "JVM_ entry",
              "JNA", "JNR-FFI", "FFM", "manual bridge", "other"]


class Graph:
    """callgraph.json + syscalls_with_callsites.txt, walked like getsyscalls_lowmem.py."""

    def __init__(self, lib_dir):
        with open(os.path.join(lib_dir, "callgraph.json")) as f:
            data = json.load(f)
        self.index, self.names = {}, []
        fn = {f["id"]: self.node("%s_%s" % (f["name"], f["addr"])) for f in data["functions"]}
        self.module = {}
        for f in data["functions"]:
            self.module.setdefault(f["name"], set()).add(os.path.basename(f["module"].replace("module-", "", 1)))
        groups = {k: array("I", (fn[m] for m in v)) for k, v in data["callee_groups"].items()}
        self.adj = {}
        self.edge_types = Counter()
        for e in data["call_graph"]:
            c = fn[e["caller_id"]]
            et = e["edge_type"]
            self.edge_types[et] += 1
            tgt = (fn[e["callee_id"]],) if e["callee_type"] == "individual" else groups[e["callee_ref"]]
            self.adj.setdefault(c, []).append((tgt, et))
        del data
        self.targets = set()
        with open(os.path.join(lib_dir, "syscalls_with_callsites.txt")) as f:
            for line in f:
                p = line.split()
                if len(p) >= 5:
                    s = self.node(p[3])
                    self.adj.setdefault(self.node(p[0] + "_" + p[1]), []).append(((s,), "syscall"))
                    self.targets.add(s)

    def node(self, name):
        i = self.index.get(name)
        if i is None:
            i = self.index[name] = len(self.names)
            self.names.append(name)
        return i

    def reach(self, starts, direct_only=False):
        """{syscall: start node name that reached it first} (BFS from all starts)."""
        seeds = {self.node(s) for s in starts}
        origin = {s: s for s in seeds}
        q = deque(seeds)
        out = {}
        while q:
            cur = q.popleft()
            if cur in self.targets:
                out[self.names[cur]] = self.names[origin[cur]]
            for tgt, et in self.adj.get(cur, ()):
                if direct_only and et == "INDIRECT":
                    continue
                for n in tgt:
                    if n not in origin:
                        origin[n] = origin[cur]
                        q.append(n)
        return out


def lib_functions(lib_dir, lib, start_syms=()):
    """name -> [addr] for functions defined by the analysed library. The module is
    the one named like the folder, plus whichever module defines SysPart's start
    functions (SysPart sometimes analyses a renamed copy, e.g. the folder
    libzstd-jni-1.5.7-2.so holds module libzstd-jni-1.5.7-2_zstd-jni-1.5.7-2.so)."""
    rows = []
    with open(os.path.join(lib_dir, "allfunctions.txt"), errors="replace") as f:
        for line in f:
            p = line.split()
            if len(p) >= 3:
                rows.append((p[0], p[1], os.path.basename(p[2].replace("module-", "", 1))))
    starts = set(start_syms)
    modules = {lib} | {mod for name, _, mod in rows if name in starts}
    funcs = {}
    for name, addr, mod in rows:
        if mod in modules:
            funcs.setdefault(name, []).append(addr)
    return funcs


def swat_symbol(sym):
    return sym if sym.startswith(("Java_", "JVM_", "netty")) else "Java_" + sym


def load_mapping(path):
    """{app: {"et": {(lib, sym): (tag, method)}, "sw": {lib: {sym: (strategy, method)}}}}"""
    out = {}
    with open(path) as f:
        for r in csv.DictReader(f):
            a = out.setdefault(r["app"], {"et": {}, "sw": {}})
            if r["et_tag"] in MAPPED_TAGS and r["et_symbol"]:
                a["et"].setdefault((r["et_lib"], r["et_symbol"]), (r["et_tag"], r["method"]))
            if r["swat_strategy"] not in ("UNMAPPED", "INTRINSIC") and r["swat_symbol"]:
                a["sw"].setdefault(os.path.basename(r["swat_lib"]), {}).setdefault(
                    swat_symbol(r["swat_symbol"]), (r["swat_strategy"], r["method"]))
    return out


def classify(et_map, lib, name):
    """Mechanism and Java method of a SysJava start symbol in lib."""
    hit = et_map.get((lib, name))
    if not hit and "__" in name:  # overload-mangled Java_..__sig: mapped under the short name
        hit = et_map.get((lib, name.split("__", 1)[0]))
    if not hit:  # same symbol mapped under a differently named copy of the library
        hit = next((v for (l, s), v in et_map.items() if s == name or s == name.split("__", 1)[0]), None)
    if hit:
        return TAG_MECH[hit[0]], hit[1]
    if name.startswith("Java_"):
        return "JNI static", ""
    if name.startswith("netty_"):
        return "RegisterNatives app", ""
    if lib == "libjvm.so":  # JDK 8 legacy Unsafe overloads (Unsafe_GetByte140, ...) the audit
        return ("JVM_ entry" if name.startswith("JVM_") else "RegisterNatives JVM"), ""  # filed elsewhere
    return "other", ""


def start_names(lib_dir):
    out = []
    for line in open(os.path.join(lib_dir, "startfuncs_with_addr.txt")):
        p = line.split()
        if p and "_" in p[0]:
            out.append(p[0])
    return out


def ffi_mechanisms(ffi_dir):
    """{(lib basename, symbol): mechanism} from jna_ffi_analysis/resolved_bindings.tsv."""
    out = {}
    path = os.path.join(ffi_dir, "resolved_bindings.tsv")
    if not os.path.isfile(path):
        return out
    with open(path) as f:
        for r in csv.DictReader(f, delimiter="\t"):
            out[(os.path.basename(r["library_file"]), r["symbol"])] = REPORT_MECH.get(r["source_report"], "other")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", nargs="+", required=True, help="label=syscalls_output_dir")
    ap.add_argument("--ffi", nargs="*", default=[], help="label=jna_ffi_analysis dir")
    ap.add_argument("--mapping", nargs="+", required=True, help="per_method.csv file(s)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    mapping = {}
    for m in args.mapping:
        mapping.update(load_mapping(m))
    ffi = dict(s.split("=", 1) for s in args.ffi)

    lib_rows, mech_rows, missed_rows, check_rows, skipped_rows = [], [], [], [], []
    for spec in args.app:
        app, root = spec.split("=", 1)
        m = mapping.get(app, {"et": {}, "sw": {}})
        libs = [(lib, os.path.join(root, lib), "syspart") for lib in sorted(os.listdir(root))]
        fmech = {}
        if app in ffi:
            fmech = ffi_mechanisms(ffi[app])
            # newer layout: libraries/<lib>; older: syscalls/<lib> without resolved_bindings.tsv
            lroot = os.path.join(ffi[app], "libraries")
            if not os.path.isdir(lroot):
                lroot = os.path.join(ffi[app], "syscalls")
            libs += [(lib, os.path.join(lroot, lib), "jna_ffi_analysis") for lib in sorted(os.listdir(lroot))]
        for lib, lib_dir, source in libs:
            if not os.path.isfile(os.path.join(lib_dir, "callgraph.json")):
                continue
            if not os.path.isfile(os.path.join(lib_dir, "startfuncs_with_addr.txt")):
                skipped_rows.append(dict(app=app, lib=lib, reason="no startfuncs_with_addr.txt in SysPart output"))
                print("skip %s %s: no start list" % (app, lib), flush=True)
                continue
            try:
                g = Graph(lib_dir)
            except ValueError as e:  # truncated callgraph.json
                skipped_rows.append(dict(app=app, lib=lib, reason="unreadable callgraph.json: %s" % e))
                print("skip %s %s: unreadable callgraph.json" % (app, lib), flush=True)
                continue
            # SysJava starts, by mechanism
            by_mech = OrderedDict()
            method_of = {}
            for s in start_names(lib_dir):
                name = s.rsplit("_", 1)[0]
                if source == "jna_ffi_analysis":
                    mech, meth = fmech.get((lib, name), "FFM" if not fmech else "other"), ""
                else:
                    mech, meth = classify(m["et"], lib, name)
                by_mech.setdefault(mech, []).append(s)
                method_of[name] = meth
            et_starts = [s for v in by_mech.values() for s in v]
            funcs = lib_functions(lib_dir, lib, {s.rsplit("_", 1)[0] for s in et_starts})
            # SWAT4J starts
            sw_starts, sw_unresolved = [], 0
            sw_by_strategy = Counter()
            sw_all = {}
            for lib_syms in m["sw"].values():
                for sym, v in lib_syms.items():
                    sw_all.setdefault(sym, v)
            named_here = set(m["sw"].get(lib, {}))
            for sym, (strategy, meth) in sorted(sw_all.items()):
                if sym in funcs:
                    sw_starts += ["%s_%s" % (sym, a) for a in funcs[sym]]
                    sw_by_strategy[strategy] += 1
                    method_of.setdefault(sym, meth)
                elif sym in named_here:
                    sw_unresolved += 1
            sw_names = {s.rsplit("_", 1)[0] for s in sw_starts}

            for mode in ("full", "direct"):
                direct = mode == "direct"
                et = g.reach(et_starts, direct)
                sw = g.reach(sw_starts, direct) if sw_starts else {}
                if mode == "full" and source == "syspart":
                    rec = {l.strip() for l in open(os.path.join(lib_dir, "syscalls.txt")) if l.strip()}
                    check_rows.append(dict(app=app, lib=lib, replay_equals_recorded=set(et) == rec,
                                           replay=len(et), recorded=len(rec)))
                per_mech = OrderedDict((k, g.reach(v, direct)) for k, v in by_mech.items())
                lib_rows.append(dict(
                    app=app, lib=lib, source=source, mode=mode,
                    sysjava_starts=len({s.rsplit("_", 1)[0] for s in et_starts}),
                    sysjava_mechanisms=" ".join("%s:%d" % (k.replace(" ", "_"), len({s.rsplit('_', 1)[0] for s in v}))
                                                for k, v in by_mech.items()),
                    swat4j_starts=len(sw_names),
                    swat4j_strategies=" ".join("%s:%d" % kv for kv in sorted(sw_by_strategy.items())),
                    swat4j_unresolved=sw_unresolved,
                    sysjava_syscalls=len(et), swat4j_syscalls=len(sw),
                    missed_by_swat4j=len(set(et) - set(sw)),
                    missed=" ".join(sorted(set(et) - set(sw))),
                    swat4j_only=" ".join(sorted(set(sw) - set(et))),
                    sysjava_set=" ".join(sorted(et)), swat4j_set=" ".join(sorted(sw))))
                for mech, reached in per_mech.items():
                    mech_rows.append(dict(
                        app=app, lib=lib, mode=mode, mechanism=mech,
                        starts=len({s.rsplit("_", 1)[0] for s in by_mech[mech]}),
                        starts_also_in_swat4j=len({s.rsplit("_", 1)[0] for s in by_mech[mech]} & sw_names),
                        syscalls=len(reached),
                        not_reached_by_swat4j=len(set(reached) - set(sw)),
                        syscalls_not_reached_by_swat4j=" ".join(sorted(set(reached) - set(sw)))))
                for sc in sorted(set(et) - set(sw)):
                    mechs = [k for k, v in per_mech.items() if sc in v]
                    start = per_mech[mechs[0]][sc].rsplit("_", 1)[0] if mechs else ""
                    missed_rows.append(dict(app=app, lib=lib, mode=mode, syscall=sc,
                                            mechanisms=" | ".join(mechs), example_start=start,
                                            java_method=method_of.get(start, "")))
            print("%-26s %-36s full SJ %3d SW %3d | direct SJ %3d SW %3d | %s" % (
                app[:26], lib[:36], lib_rows[-2]["sysjava_syscalls"], lib_rows[-2]["swat4j_syscalls"],
                lib_rows[-1]["sysjava_syscalls"], lib_rows[-1]["swat4j_syscalls"], lib_rows[-1]["sysjava_mechanisms"]),
                flush=True)

    def write(name, rows):
        if not rows:
            return
        with open(os.path.join(args.out, name), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    mech_rows.sort(key=lambda r: (r["app"], r["lib"], r["mode"], MECH_ORDER.index(r["mechanism"])))
    write("per_library.csv", lib_rows)
    write("mechanisms.csv", mech_rows)
    write("missed.csv", missed_rows)
    write("check.csv", check_rows)
    write("skipped.csv", skipped_rows)


if __name__ == "__main__":
    main()
