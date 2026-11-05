#!/usr/bin/env python3
"""
Shortest call path from an entry point to a syscall in one SysPart library graph.

  trace_path.py <lib_dir> <start_function> <syscall> [--direct]

<lib_dir> holds callgraph.json, syscalls_with_callsites.txt (a SysPart output folder).
--direct ignores INDIRECT edges (the address-taken over-approximation), as the
"direct" mode of mechanism_ablation.py does. Used for the case-study paths in
MAPPING_PER_LIBRARY.md.
"""
import argparse
import os
import sys
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mechanism_ablation import Graph  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lib_dir")
    ap.add_argument("start")
    ap.add_argument("syscall")
    ap.add_argument("--direct", action="store_true")
    args = ap.parse_args()
    g = Graph(args.lib_dir)
    seeds = {i for n, i in g.index.items() if n.rsplit("_", 1)[0] == args.start}
    if not seeds:
        sys.exit("start function %s not in graph" % args.start)
    parent = {s: (None, None) for s in seeds}
    q = deque(seeds)
    while q:
        cur = q.popleft()
        if g.names[cur] == args.syscall:
            hops = []
            while cur is not None:
                prev, et = parent[cur]
                if prev is not None:
                    hops.append("%s -[%s]-> %s" % (g.names[prev], et, g.names[cur]))
                cur = prev
            print("\n".join(reversed(hops)))
            return
        for tgt, et in g.adj.get(cur, ()):
            if args.direct and et == "INDIRECT":
                continue
            for n in tgt:
                if n not in parent:
                    parent[n] = (cur, et)
                    q.append(n)
    sys.exit("%s not reachable from %s" % (args.syscall, args.start))


if __name__ == "__main__":
    main()
