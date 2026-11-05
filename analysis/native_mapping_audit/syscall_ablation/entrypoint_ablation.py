#!/usr/bin/env python3
"""
Entry-point ablation: does SysJava's native mapping change the syscall set?

For each analysed library, the binaries and the SysPart call graph (built with
debug symbols) are held fixed. Only the start functions change:

  sysjava  - SysPart's own start list (startfuncs_with_addr.txt), i.e. the
             functions SysJava's mapper emitted for this library
  swat4j   - the functions SWAT4J's mapping assigns to a library of the same name
             (out/per_method.csv from ../audit_native_mapping.py)

Reachability is replayed with EchoTrace/scripts/getsyscalls_lowmem.py, the same
BFS SysPart's getsyscalls.py performs. For every syscall reached only from the
SysJava starts the logged call path is kept as evidence.

Writes, under out/:
  per_library.csv      start counts and syscall sets per (app, library)
  per_app.csv          union over each app's Java libraries
  sysjava_only.csv     one row per syscall SWAT4J's mapping misses, with path
  check.csv            replaying SysJava's starts reproduces syscalls.txt?
"""
import argparse
import csv
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
GETSYSCALLS = os.path.expanduser("~/Tutorial/EchoTrace/scripts/getsyscalls_lowmem.py")
MAPPED_TAGS = {"JNI", "JNI_DYNAMIC", "REGISTERED", "JVM", "NETTY", "JVM_BUILTIN",
               "DIRECT_LIBC_BRIDGE", "SIGAR_LIST_BRIDGE"}


def swat_symbol(sym):
    """SWAT4J keeps some JNI names without the Java_ prefix (it later matches by
    suffix); the function it means is the Java_-prefixed one."""
    return sym if sym.startswith(("Java_", "JVM_", "netty")) else "Java_" + sym


def load_mapping(per_method_csv):
    """{(app, lib basename): {"swat4j": set(sym), "sysjava": set(sym), "method": {sym: method}}}"""
    out = {}
    with open(per_method_csv) as f:
        for r in csv.DictReader(f):
            if r["swat_strategy"] not in ("UNMAPPED", "INTRINSIC") and r["swat_symbol"]:
                key = (r["app"], os.path.basename(r["swat_lib"]))
                e = out.setdefault(key, {"swat4j": set(), "sysjava": set(), "method": {}})
                s = swat_symbol(r["swat_symbol"])
                e["swat4j"].add(s)
                e["method"].setdefault(s, r["method"])
            if r["et_tag"] in MAPPED_TAGS and r["et_symbol"]:
                key = (r["app"], r["et_lib"])
                e = out.setdefault(key, {"swat4j": set(), "sysjava": set(), "method": {}})
                e["sysjava"].add(r["et_symbol"])
                e["method"].setdefault(r["et_symbol"], r["method"])
    return out


def module_functions(lib_dir, lib):
    """name -> [addr] for functions whose module is this library."""
    funcs = {}
    with open(os.path.join(lib_dir, "allfunctions.txt"), errors="replace") as f:
        for line in f:
            parts = line.split()
            if len(parts) < 3:
                continue
            if os.path.basename(parts[2].replace("module-", "", 1)) != lib:
                continue
            funcs.setdefault(parts[0], []).append(parts[1])
    return funcs


def reach(lib_dir, starts, log=None):
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as t:
        t.write("\n".join(starts) + "\n")
        path = t.name
    cmd = [sys.executable, GETSYSCALLS, os.path.join(lib_dir, "callgraph.json"),
           os.path.join(lib_dir, "syscalls_with_callsites.txt"), path]
    if log:
        cmd += ["--log", log]
    r = subprocess.run(cmd, capture_output=True, text=True)
    os.unlink(path)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-2000:])
    return {l.strip() for l in r.stdout.splitlines() if l.strip()}


def parse_paths(log):
    paths, cur, lines = {}, None, []
    if not os.path.isfile(log):
        return paths
    for line in open(log, errors="replace"):
        m = re.match(r"^Path to (\S+):", line)
        if m:
            if cur:
                paths[cur] = lines
            cur, lines = m.group(1), []
        elif cur and line.strip():
            lines.append(line.strip())
    if cur:
        paths[cur] = lines
    return paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", nargs="+", required=True, help="label=binary_analysis_dir")
    ap.add_argument("--mapping", default=os.path.join(HERE, "..", "out", "per_method.csv"))
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    logs = os.path.join(args.out, "logs")
    os.makedirs(logs, exist_ok=True)
    mapping = load_mapping(args.mapping)

    lib_rows, app_rows, only_rows, check_rows = [], [], [], []
    for spec in args.app:
        app, root = spec.split("=", 1)
        root = os.path.expanduser(root)
        app_et, app_sw = set(), set()
        for lib in sorted(os.listdir(root)):
            lib_dir = os.path.join(root, lib)
            if not os.path.isfile(os.path.join(lib_dir, "callgraph.json")):
                continue
            funcs = module_functions(lib_dir, lib)
            et_starts = [l.split()[0] for l in open(os.path.join(lib_dir, "startfuncs_with_addr.txt")) if l.strip()]
            m = mapping.get((app, lib), {"swat4j": set(), "sysjava": set(), "method": {}})
            sw_starts, sw_missing = [], []
            for s in sorted(m["swat4j"]):
                if s in funcs:
                    sw_starts += ["%s_%s" % (s, a) for a in funcs[s]]
                else:
                    sw_missing.append(s)
            log = os.path.join(logs, "%s__%s.sysjava.log" % (app, lib))
            et = reach(lib_dir, et_starts, log=log)
            sw = reach(lib_dir, sw_starts) if sw_starts else set()
            recorded = {l.strip() for l in open(os.path.join(lib_dir, "syscalls.txt")) if l.strip()}
            check_rows.append(dict(app=app, lib=lib, replay_equals_recorded=et == recorded,
                                   replay=len(et), recorded=len(recorded)))
            app_et |= et
            app_sw |= sw
            et_names = {s.rsplit("_", 1)[0] for s in et_starts}
            sw_names = {s.rsplit("_", 1)[0] for s in sw_starts}
            lib_rows.append(dict(app=app, lib=lib,
                                 sysjava_starts=len(et_names), swat4j_starts=len(sw_names),
                                 sysjava_only_starts=len(et_names - sw_names),
                                 swat4j_unresolved=len(sw_missing),
                                 sysjava_syscalls=len(et), swat4j_syscalls=len(sw),
                                 sysjava_only=" ".join(sorted(et - sw)),
                                 swat4j_only=" ".join(sorted(sw - et))))
            paths = parse_paths(log)
            for sc in sorted(et - sw):
                p = paths.get(sc, [])
                start = p[0].split(" - ")[0] if p else ""
                sname = start.rsplit("_", 1)[0]
                only_rows.append(dict(app=app, lib=lib, syscall=sc,
                                      start_function=sname,
                                      java_method=m["method"].get(sname, ""),
                                      start_in_swat4j=sname in sw_names,
                                      path=" | ".join(p)))
        app_rows.append(dict(app=app, sysjava=len(app_et), swat4j=len(app_sw),
                             sysjava_only=" ".join(sorted(app_et - app_sw)),
                             swat4j_only=" ".join(sorted(app_sw - app_et))))
        print(app, "SysJava", len(app_et), "SWAT4J-mapping", len(app_sw), "missed:", sorted(app_et - app_sw))

    def write(name, rows):
        with open(os.path.join(args.out, name), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    write("per_library.csv", lib_rows)
    write("per_app.csv", app_rows)
    write("check.csv", check_rows)
    if only_rows:
        write("sysjava_only.csv", only_rows)


if __name__ == "__main__":
    main()
