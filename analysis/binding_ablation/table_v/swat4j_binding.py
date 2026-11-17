#!/usr/bin/env python3
"""Table V, SWAT4J binding column: the native methods SWAT4J identifies (its own JTracer list), mapped to native
targets by SysJava's mapping, and SysJava's call graphs walked from those targets. Also re-walks the full SysJava
binding arm from the same files as a check (it must give the paper's Binding syscalls).

Reads only shipped files of this artifact:
  2_swat4j_vs_sysjava/sysjava_results/<img>/Binary_Analysis/syscalls_output_<img>/<lib>/callgraph.json.gz,
      syscalls_with_callsites.txt, startfuncs_resolved.txt     (SysPart call graph per library, incl. libjvm.so)
  .../Binary_Analysis/jna_ffi_analysis/syscalls/<lib>/           (JNA-bound libraries)
  .../Binary_Analysis/extra_components/jvm_internal_imports/syscalls.txt   (libjvm's imports: the JVM itself)
  .../Bytecode_Analysis/outputs_<img>/{mapped,manual_mapped}_method_syscalls.txt, jna_hits.txt   (SysJava's mapping)
  swat4j/outputs/static/native_methods/<app>.txt                 (SWAT4J's native-method list)
  2_swat4j_vs_sysjava/manual_mapping/orientdb_3.2.19-jdk8-buster/syspart_libjffi-1.2.so/syscalls.txt and
  inputs/jruby_jnr/syscalls.txt                                  (two binding runs the pipeline does not make)
Usage: python3 swat4j_binding.py      -> results/swat4j_binding.tsv (+ table printed)"""
import collections, csv, glob, gzip, json, os, re

H = os.path.dirname(os.path.abspath(__file__))
ART = os.path.abspath(os.path.join(H, "..", "..", ".."))
RES = f"{ART}/2_swat4j_vs_sysjava/sysjava_results"
SWN = f"{ART}/swat4j/outputs/static/native_methods"
IMAGES = ["zookeeper_3.4.14", "tomcat_7.0", "cassandra_3.0.29", "jetty_9.4.51", "storm_2.4.0", "orientdb_3.2.19",
          "elasticsearch_7.5.2", "solr_8.7.0", "groovy_4.0.0", "jruby_9.4.2.0"]
PAPER_BINDING = [113, 128, 127, 100, 133, 115, 118, 131, 113, 104]
ALIASES = {"pread": "pread64", "pwrite": "pwrite64"}


def names(p):
    try:
        return {ALIASES.get(l.split()[0], l.split()[0]) for l in open(p, errors="replace") if l.strip()}
    except FileNotFoundError:
        return set()


class Graph:
    """SysPart call graph of one library: syscalls reachable from a set of start functions."""
    def __init__(self, d):
        g = json.load(gzip.open(f"{d}/callgraph.json.gz", "rt"))
        self.byname = collections.defaultdict(list)
        for f in g["functions"]:
            self.byname[f["name"]].append(f["id"])
        self.name = {f["id"]: f["name"] for f in g["functions"]}
        self.adj = collections.defaultdict(list)
        for e in g["call_graph"]:
            self.adj[e["caller_id"]] += g["callee_groups"][e["callee_ref"]] if e["callee_type"] == "group" else [e["callee_id"]]
        self.sys = collections.defaultdict(set)
        for l in open(f"{d}/syscalls_with_callsites.txt", errors="replace"):
            p = l.split()
            if len(p) >= 5:
                self.sys[p[0]].add(ALIASES.get(p[3], p[3]))

    def reach(self, starts):
        seen = {i for s in starts for i in self.byname.get(s, [])}
        stack = list(seen)
        while stack:
            for c in self.adj.get(stack.pop(), []):
                if c not in seen:
                    seen.add(c); stack.append(c)
        out = set().union(*(self.sys.get(self.name[i], set()) for i in seen)) if seen else set()
        return out.union(*(self.sys.get(s, set()) for s in starts)) if starts else out


def main():
    rows = []
    for img_short, paper in zip(IMAGES, PAPER_BINDING):
        img = f"{img_short}-jdk8-buster"; app = img_short.split("_")[0]
        b, o = f"{RES}/{img}/Binary_Analysis", f"{RES}/{img}/Bytecode_Analysis/outputs_{img}"
        swat = names(f"{SWN}/{app}.txt")
        nat_tgt = collections.defaultdict(set)              # (library file name, symbol) -> Java natives
        for f in (f"{o}/mapped_method_syscalls.txt", f"{o}/manual_mapped_method_syscalls.txt"):
            for l in open(f, errors="replace") if os.path.exists(f) else []:
                m = re.match(r"(\S+?):(\S+) -> (\S+) \[", l)
                if m and "NOT_FOUND" not in l:
                    nat_tgt[(os.path.basename(m.group(1)), m.group(3))].add(m.group(2))
        full, sw, methods, starts = set(), set(), set(), 0
        for d in sorted(glob.glob(f"{b}/syscalls_output_{img}/*/callgraph.json.gz")):
            d = os.path.dirname(d); lib = os.path.basename(d)
            bst = names(f"{d}/startfuncs_resolved.txt")
            sst = {s for s in bst if nat_tgt.get((lib, s), set()) & swat}
            g = Graph(d)
            full |= g.reach(bst)
            if sst:
                sw |= g.reach(sst); starts += len(sst)
                for s in sst:
                    methods |= nat_tgt[(lib, s)] & swat
        hits = []
        if os.path.exists(f"{o}/jna_hits.txt"):
            hits = [[x.strip() for x in l.rstrip("\n").split(" | ")] for l in open(f"{o}/jna_hits.txt", errors="replace")]
            hits = [h for h in hits if len(h) >= 4]
        false_syms = {h[3] for h in hits if h[0] == "ffi"}        # JDK 8 has no FFM API: these hits are false
        def jside(s):
            m = re.match(r"<([^:]+): \S+ ([^(]+)\(", s)
            return f"{m.group(1)}.{m.group(2)}" if m else s
        for sd in sorted(glob.glob(f"{b}/jna_ffi_analysis/syscalls/*/")):
            sd = sd.rstrip("/"); lib = os.path.basename(sd)
            st = names(f"{b}/jna_ffi_analysis/startfuncs/{lib}.txt")
            if st and st <= false_syms:
                continue
            full |= names(f"{sd}/syscalls.txt")
            fn = {h[3] for h in hits if h[0] != "ffi" and jside(h[1]) in swat}
            sst = names(f"{sd}/startfuncs_resolved.txt") & fn
            if sst:
                sw |= Graph(sd).reach(sst); starts += len(sst)
                methods |= {jside(h[1]) for h in hits if h[0] != "ffi" and jside(h[1]) in swat and h[3] in sst}
        imports = names(f"{b}/extra_components/jvm_internal_imports/syscalls.txt")   # the JVM itself: both arms
        full |= imports; sw |= imports
        if app == "jruby":
            full |= names(f"{H}/inputs/jruby_jnr/syscalls.txt")
        if app == "orientdb":
            full |= names(f"{ART}/2_swat4j_vs_sysjava/manual_mapping/{img}/syspart_libjffi-1.2.so/syscalls.txt")
        rows.append([img, paper, len(full), len(swat), len(methods), starts, len(sw),
                     " ".join(sorted(full - sw)), " ".join(sorted(sw - full))])
        print(f"{img:34s} binding {len(full):3d} (paper {paper})  SWAT4J natives {len(methods):5d}  syscalls {len(sw):3d}", flush=True)

    os.makedirs(f"{H}/results", exist_ok=True)
    with open(f"{H}/results/swat4j_binding.tsv", "w", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["image", "paper_binding_syscalls", "rewalked_binding_syscalls", "swat4j_listed_natives",
                    "swat4j_natives_resolved_by_sysjava", "swat4j_start_functions", "swat4j_syscalls",
                    "only_binding", "only_swat4j"])
        w.writerows(rows)


if __name__ == "__main__":
    main()
