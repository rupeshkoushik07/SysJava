#!/usr/bin/env python3
"""Reachable syscalls from SysPart's -a 23 call graph, without the JSON step.

Same answer as `parse_callgraph_to_json.py | getsyscalls.py`, but keeps only a
deduplicated integer adjacency, so a call graph rooted at every libjvm function
(which pushed parse_callgraph_to_json.py past 36 GB) fits in a few GB.

The original pipeline's naming rules are kept:
  - a function node is keyed by name; its address is the first one seen for
    that name (caller before callee on each line), node string = name_addr
  - a syscall edge from syscalls_with_callsites.txt (name addr ... syscall)
    attaches to name_addr; if that string is not a call-graph node it is a
    separate node, reachable only when it is itself a start function
  - start functions are name_addr strings; one matching no node is isolated

Usage: syspart ... -a 23 | lean_syscalls.py - <syscalls_with_callsites> <startfuncs_with_addr>
"""
import sys

cg_arg, sys_file, start_file = sys.argv[1:4]

ids = {}      # function name -> node id
node = []     # node id -> name_addr
adj = []      # node id -> set of callee ids


def nid(name, addr):
    i = ids.get(name)
    if i is None:
        i = ids[name] = len(node)
        node.append(f"{name}_{addr}")
        adj.append(set())
    return i


lines = 0
with (sys.stdin if cg_arg == "-" else open(cg_arg)) as cg:
    for line in cg:
        p = line.split()
        if len(p) < 8:
            continue
        lines += 1
        caller = nid(p[3], p[7])
        adj[caller].add(nid(p[5], p[4]))

by_string = {s: i for i, s in enumerate(node)}
extra = {}        # syscall-site strings that are not call-graph nodes
node_sys = {}     # node id or extra string -> syscalls
with open(sys_file) as f:
    for line in f:
        p = line.split()
        if len(p) < 5:
            continue
        src = f"{p[0]}_{p[1]}"
        key = by_string.get(src, src)
        node_sys.setdefault(key, set()).add(p[3])

seen = set()
stack = []
reached = set()
with open(start_file) as f:
    for line in f:
        p = line.split()
        if not p:
            continue
        i = by_string.get(p[0])
        if i is None:
            reached |= node_sys.get(p[0], set())   # isolated start
        elif i not in seen:
            seen.add(i)
            stack.append(i)

while stack:
    i = stack.pop()
    reached |= node_sys.get(i, set())
    for j in adj[i]:
        if j not in seen:
            seen.add(j)
            stack.append(j)

print(f"edge lines={lines} functions={len(node)} "
      f"unique edges={sum(len(a) for a in adj)} reachable={len(seen)}", file=sys.stderr)
for s in sorted(reached):
    print(s)
