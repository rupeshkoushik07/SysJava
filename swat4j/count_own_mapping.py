#!/usr/bin/env python3
"""Count SWAT4J's own native-to-JNI mapping, read-only, for one app of a run_swat4j_host_out.sh run.

SWAT4J prints no per-method mapping counts. This imports SWAT4J's unmodified binary_analyser.py from
the app's work folder, builds its six maps with its own functions (run it inside the same mount
namespace as the run, so /home/mrx/Desktop and /usr/local/apr/lib are the app's), and replays the
rules of its aggregate() on SWAT4J's own <name>_native.txt:
  - a method that is a key of the merged map (update order: Java_ host JDK, JVM_ source table,
    jffi, netty, tcnative, sigar) is mapped by the map that supplied the key: JVM_XXX for the JVM
    table, Java_XXX for the others (all are Java_* symbol-name lookups);
  - an io.netty method whose last name segment is the suffix of a "netty*" key is NETTY_HEURISTIC
    (aggregate() adds every such function).
Writes <out>/<app>.tsv (method, strategy, symbol, library) and prints one summary line.

Usage: count_own_mapping.py <work_dir> <libs_dir> <native_txt> <out_dir> <app>
"""
import contextlib, io, os, sys

work, libs, native_txt, out, app = sys.argv[1:6]
sys.path.insert(0, work)
os.chdir(work)
import binary_analyser as ba   # SWAT4J, unmodified

with contextlib.redirect_stdout(io.StringIO()):
    maps = [("Java_XXX", ba.build_map()), ("JVM_XXX", ba.build_JVM_map()),
            ("Java_XXX", ba.build_jffi_map(libs)), ("Java_XXX", ba.build_netty_map(libs)),
            ("Java_XXX", ba.build_tc_map(libs)), ("Java_XXX", ba.build_org_map(libs))]
merged, source = {}, {}
for strat, m in maps:
    merged.update(m)
    for k in m:
        source[k] = strat

methods = [l.strip("\n") for l in open(native_txt)]
rows = []
for m in dict.fromkeys(methods):   # SWAT4J's list may repeat a method; count each once
    if m in merged:
        sym, lib = merged[m].split(" ")
        rows.append((m, source[m], sym, lib))
        continue
    if m.startswith("io.netty"):
        end = m.split(".")[-1]
        hits = [n for n in merged if n.startswith("netty") and n.endswith(end)]
        if hits:
            rows.append((m, "NETTY_HEURISTIC", ",".join(merged[h].split(" ")[0] for h in hits),
                         merged[hits[0]].split(" ")[1]))
            continue
    rows.append((m, "UNMAPPED", "", ""))

os.makedirs(out, exist_ok=True)
with open(f"{out}/{app}.tsv", "w") as f:
    f.write("method\tstrategy\tsymbol\tlibrary\n")
    for r in rows:
        f.write("\t".join(r) + "\n")
c = {s: sum(r[1] == s for r in rows) for s in ("Java_XXX", "JVM_XXX", "NETTY_HEURISTIC", "UNMAPPED")}
print(f"{app}\tlines={len(methods)}\tdistinct={len(rows)}\t" + "\t".join(f"{k}={v}" for k, v in c.items()))
