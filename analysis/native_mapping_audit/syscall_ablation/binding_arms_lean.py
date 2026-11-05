#!/usr/bin/env python3
"""
Extra entry-point arms over the debug-symbol ablation graphs of EchoTrace/ablation
(run_ablation.sh, variant G: one SysPart -a 23 call graph per library, rooted at every
function of the library, kept as A/<lib>/callgraph_a23.txt.zst).

That run already gives two arms:
  A  no binding: every function of the library (exported or not)
  B  SysJava binding: the bound start functions
This adds, over the same graph and with the same reachability rules (lean_syscalls.py):
  E  no binding, exported only: every function the .so exports (nm -D, T/W/i)
  S  SWAT4J binding: the symbols SWAT4J's (unmodified) mapping produced, wherever it
     placed them, that the analysed library defines (same fair credit as
     mechanism_ablation.py)
and recomputes A and B as a check against the run's own syscalls.txt.

Also writes starts/<arm>/<lib>.txt (the start-function names of each arm) and why.csv:
for every syscall one arm reaches and the other does not, the start functions that reach
it (for no binding vs SysJava, only the exported functions SysJava did not bind; at most
10 names listed, n_start_functions counts all).

The ablation folder is only read. Libraries whose graph is not finished yet are listed
as pending.

  binding_arms_lean.py --ablation ~/Tutorial/EchoTrace/ablation/tomcat_11.0.22 \
      --swat swat4j_latest/tomcat_11.0.22/swat4j_mapped_methods.txt --out <dir>
"""
import argparse
import csv
import os
import subprocess

ARMS = ["A", "E", "B", "S"]
NAMES = {"A": "no_binding_all", "E": "no_binding_exports", "B": "sysjava", "S": "swat4j"}


def swat_symbols(path):
    """SWAT4J symbols; JNI names it keeps without the Java_ prefix get it back."""
    syms = {}
    with open(path) as f:
        for line in f:
            if " -> " not in line or " @ " not in line:
                continue
            method, rest = line.split(" -> ", 1)
            sym, rest = rest.split(" @ ", 1)
            sym = sym.strip()
            strategy = rest.rsplit("[", 1)[-1].rstrip("]\n ")
            if not sym.startswith(("Java_", "JVM_", "netty")):
                sym = "Java_" + sym
            syms.setdefault(sym, (strategy, method.strip()))
    return syms


def exports(path):
    out = subprocess.run(["nm", "-D", "--defined-only", path], check=True,
                         capture_output=True, text=True).stdout
    return {p[2].split("@", 1)[0] for p in (l.split() for l in out.splitlines())
            if len(p) == 3 and p[1] in "TWi"}


class LeanGraph:
    """lean_syscalls.py's graph, loaded once so several start sets can be walked."""

    def __init__(self, cg_zst, sys_file):
        self.ids, self.node, self.adj = {}, [], []
        proc = subprocess.Popen(["zstdcat", cg_zst], stdout=subprocess.PIPE, text=True)
        for line in proc.stdout:
            p = line.split()
            if len(p) < 8:
                continue
            caller = self.nid(p[3], p[7])
            self.adj[caller].add(self.nid(p[5], p[4]))
        if proc.wait() != 0:
            raise RuntimeError("zstdcat failed on %s" % cg_zst)
        self.by_string = {s: i for i, s in enumerate(self.node)}
        self.node_sys = {}
        with open(sys_file) as f:
            for line in f:
                p = line.split()
                if len(p) < 5:
                    continue
                src = "%s_%s" % (p[0], p[1])
                self.node_sys.setdefault(self.by_string.get(src, src), set()).add(p[3])

    def starts_reaching(self, syscall, starts):
        """The starts (name_addr strings) from which `syscall` is reachable (reverse BFS)."""
        if not hasattr(self, "rev"):
            self.rev = [[] for _ in self.node]
            for i, out in enumerate(self.adj):
                for j in out:
                    self.rev[j].append(i)
        want = set(starts)
        hits = {k for k, v in self.node_sys.items() if isinstance(k, str) and syscall in v and k in want}
        seen = [i for i in self.node_sys if isinstance(i, int) and syscall in self.node_sys[i]]
        seen, stack = set(seen), list(seen)
        while stack:
            i = stack.pop()
            if self.node[i] in want:
                hits.add(self.node[i])
            for j in self.rev[i]:
                if j not in seen:
                    seen.add(j)
                    stack.append(j)
        return sorted(h.rsplit("_", 1)[0] for h in hits)

    def nid(self, name, addr):
        i = self.ids.get(name)
        if i is None:
            i = self.ids[name] = len(self.node)
            self.node.append("%s_%s" % (name, addr))
            self.adj.append(set())
        return i

    def reach(self, starts):
        seen, stack, reached = set(), [], set()
        for s in starts:
            i = self.by_string.get(s)
            if i is None:
                reached |= self.node_sys.get(s, set())
            elif i not in seen:
                seen.add(i)
                stack.append(i)
        while stack:
            i = stack.pop()
            reached |= self.node_sys.get(i, set())
            for j in self.adj[i]:
                if j not in seen:
                    seen.add(j)
                    stack.append(j)
        return reached


def own_functions(allfunctions, lib):
    """name -> name_addr for functions of the library's own module (run_ablation.sh rule)."""
    out = {}
    with open(allfunctions, errors="replace") as f:
        for line in f:
            p = line.split()
            if len(p) >= 3 and os.path.basename(p[2].replace("module-", "", 1)) == lib:
                out.setdefault(p[0], "%s_%s" % (p[0], p[1]))
    return out


def lines(path):
    with open(path) as f:
        return [l.strip() for l in f if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ablation", required=True, help="EchoTrace/ablation/<img> folder")
    ap.add_argument("--swat", required=True, help="SWAT4J swat4j_mapped_methods.txt")
    ap.add_argument("--rest", nargs="*", default=[],
                    help="syscall lists the deployed profile adds regardless of mapping")
    ap.add_argument("--profile", help="recorded final profile, as a check of arm B")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    sw = swat_symbols(args.swat)

    targets = {}
    for t in sorted(f for f in os.listdir(args.ablation) if f.startswith("targets_") and f.endswith(".tsv")):
        for row in csv.reader(open(os.path.join(args.ablation, t)), delimiter="\t"):
            if len(row) >= 3:
                targets.setdefault(row[0], (row[1], row[2]))

    rows, pending, why_rows, union = [], [], [], {a: set() for a in ARMS}
    for lib, (libpath, _) in sorted(targets.items()):
        adir, bdir = (os.path.join(args.ablation, v, lib) for v in ("A", "B"))
        cg = os.path.join(adir, "callgraph_a23.txt.zst")
        if not (os.path.isfile(os.path.join(adir, "syscalls.txt"))
                and os.path.isfile(os.path.join(bdir, "syscalls.txt")) and os.path.isfile(cg)):
            pending.append(dict(lib=lib, reason="ablation graph not finished"))
            print("pending %s" % lib, flush=True)
            continue
        g = LeanGraph(cg, os.path.join(adir, "syscalls_with_callsites.txt"))
        funcs = own_functions(os.path.join(adir, "allfunctions.txt"), lib)
        exp = exports(libpath)
        starts = {
            "A": lines(os.path.join(adir, "startfuncs_with_addr.txt")),
            "B": lines(os.path.join(bdir, "startfuncs_with_addr.txt")),
            "E": [funcs[n] for n in sorted(exp) if n in funcs],
            "S": [funcs[n] for n in sorted(sw) if n in funcs],
        }
        for a, s in starts.items():
            sdir = os.path.join(args.out, "starts", NAMES[a])
            os.makedirs(sdir, exist_ok=True)
            with open(os.path.join(sdir, lib + ".txt"), "w") as f:
                f.writelines(n.rsplit("_", 1)[0] + "\n" for n in sorted(s))
        sets = {a: g.reach(s) for a, s in starts.items()}
        recorded = {a: set(lines(os.path.join(d, "syscalls.txt"))) for a, d in (("A", adir), ("B", bdir))}
        for a in ARMS:
            union[a] |= sets[a]
        # which start functions explain each differing syscall
        for (x, y) in (("E", "B"), ("B", "S")):
            extra_starts = [st for st in starts[x] if st not in set(starts[y])]
            for sc in sorted(sets[x] - sets[y]):
                who = g.starts_reaching(sc, extra_starts if x == "E" else starts[x])
                why_rows.append(dict(lib=lib, comparison="%s_not_%s" % (NAMES[x], NAMES[y]), syscall=sc,
                                     n_start_functions=len(who), start_functions=" ".join(who[:10])))
        strategies = sorted({sw[n][0] for n in sw if n in funcs})
        rows.append(dict(
            lib=lib, functions=len(funcs), exported=len(starts["E"]),
            **{"%s_starts" % NAMES[a]: len(starts[a]) for a in ARMS},
            swat4j_strategies=" ".join(strategies),
            **{"%s_syscalls" % NAMES[a]: len(sets[a]) for a in ARMS},
            check_A_equals_ablation=sets["A"] == recorded["A"],
            check_B_equals_ablation=sets["B"] == recorded["B"],
            exports_minus_sysjava=" ".join(sorted(sets["E"] - sets["B"])),
            all_minus_exports=" ".join(sorted(sets["A"] - sets["E"])),
            sysjava_minus_swat4j=" ".join(sorted(sets["B"] - sets["S"])),
            swat4j_minus_sysjava=" ".join(sorted(sets["S"] - sets["B"])),
            **{"%s_set" % NAMES[a]: " ".join(sorted(sets[a])) for a in ARMS}))
        print("%-26s A %3d E %3d B %3d S %3d | starts A %5d E %4d B %3d S %3d | check A %s B %s" % (
            lib, *(len(sets[a]) for a in ARMS), *(len(starts[a]) for a in ARMS),
            rows[-1]["check_A_equals_ablation"], rows[-1]["check_B_equals_ablation"]), flush=True)
        del g

    cont = [dict(libraries=" ".join(r["lib"] for r in rows), pending=" ".join(p["lib"] for p in pending),
                 **{"%s_syscalls" % NAMES[a]: len(union[a]) for a in ARMS},
                 exports_minus_sysjava=" ".join(sorted(union["E"] - union["B"])),
                 all_minus_exports=" ".join(sorted(union["A"] - union["E"])),
                 sysjava_minus_swat4j=" ".join(sorted(union["B"] - union["S"])),
                 **{"%s_set" % NAMES[a]: " ".join(sorted(union[a])) for a in ARMS})]

    profile = []
    if args.rest:
        rest = set().union(*(set(lines(p)) for p in args.rest))
        recorded = set(lines(args.profile)) if args.profile else None
        prof = {a: rest | union[a] for a in ARMS}
        for a in ARMS:
            profile.append(dict(arm=NAMES[a], syscalls=len(prof[a]),
                                vs_sysjava_added=" ".join(sorted(prof[a] - prof["B"])),
                                vs_sysjava_missing=" ".join(sorted(prof["B"] - prof[a])),
                                equals_recorded_profile="" if recorded is None else prof[a] == recorded,
                                set=" ".join(sorted(prof[a]))))

    for name, data in (("per_library.csv", rows), ("container.csv", cont),
                       ("profile.csv", profile), ("pending.csv", pending),
                       ("why.csv", why_rows)):
        path = os.path.join(args.out, name)
        if not data:
            if os.path.exists(path):
                os.remove(path)
            continue
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0].keys()))
            w.writeheader()
            w.writerows(data)


if __name__ == "__main__":
    main()
