#!/usr/bin/env python3
"""Low-memory drop-in for SysPartCode's getsyscalls.py.

The original expands every callee group of callgraph.json into one edge per
member, builds a fresh "name_addr" string for each, and stores every edge twice
(forward and reverse). A full libjvm graph has groups of thousands of
address-taken targets at thousands of indirect callsites, so it ran out of
memory on a 48 MB JSON file. This version keeps groups as shared member lists
and walks them in place.

It reproduces the original's breadth-first search exactly: same neighbour order
(call_graph records in file order, group members in listed order, then the
function's syscall sites), so the reachable syscalls and the paths written with
--log are the same. The original also parsed the JSON text a second time as if
it were raw SysPart output; that only added nodes made of JSON punctuation that
no start function can reach, so it is skipped.

Usage (same as the original):
  getsyscalls_lowmem.py callgraph.json syscalls_with_callsites.txt startfuncs_with_addr.txt [--log logfile]
"""

import argparse
import json
import logging
from array import array
from collections import deque


def main():
    parser = argparse.ArgumentParser(description="Compute reachable syscalls from startfunc")
    parser.add_argument("args1", help="Callgraph file")
    parser.add_argument("args2", help="Syscalls with callsite info")
    parser.add_argument("args3", help="file with list of start functions")
    parser.add_argument("--log", type=str, help="Enable logging")
    args = parser.parse_args()
    if args.log:
        logging.basicConfig(filename=args.log, filemode="w", level=logging.DEBUG, format="%(message)s")
    else:
        logging.basicConfig(level=logging.CRITICAL)

    with open(args.args1) as handle:
        data = json.load(handle)

    # Node names are "<name>_<addr>", as in the original; functions sharing a
    # name_addr collapse into one node there too.
    node_index = {}
    node_names = []

    def node(name):
        index = node_index.get(name)
        if index is None:
            index = node_index[name] = len(node_names)
            node_names.append(name)
        return index

    func_node = {f["id"]: node(f"{f['name']}_{f['addr']}") for f in data["functions"]}
    del data["functions"]

    edge_types = []
    edge_type_index = {}

    def edge_type(name):
        index = edge_type_index.get(name)
        if index is None:
            index = edge_type_index[name] = len(edge_types)
            edge_types.append(name)
        return index

    groups = {name: array("I", (func_node[m] for m in members))
              for name, members in data["callee_groups"].items()}
    del data["callee_groups"]

    # Adjacency in insertion order: (kind, target, edge_type) where kind 0 is a
    # single callee node and kind 1 a callee group.
    adjacency = {}
    for edge in data["call_graph"]:
        caller = func_node[edge["caller_id"]]
        etype = edge_type(edge["edge_type"])
        if edge["callee_type"] == "individual":
            entry = (0, func_node[edge["callee_id"]], etype)
        else:
            entry = (1, edge["callee_ref"], etype)
        adjacency.setdefault(caller, []).append(entry)
    del data

    targets = set()
    syscall_type = edge_type("syscall")
    with open(args.args2) as handle:
        for line in handle:
            parts = line.strip().split()
            if len(parts) >= 5:
                syscall = node(parts[3])
                adjacency.setdefault(node(parts[0] + "_" + parts[1]), []).append((0, syscall, syscall_type))
                targets.add(syscall)

    startfuncs = []
    with open(args.args3) as handle:
        for line in handle:
            parts = line.strip().split()
            if parts:
                startfuncs.append(node(parts[0]))
    # The original seeds its queue from a set; keep the same set semantics.
    start_set = set(startfuncs)

    visited = set(start_set)
    parent = {s: (None, None) for s in start_set}
    reachable = set()
    queue = deque(start_set)
    while queue:
        current = queue.popleft()
        if current in targets:
            reachable.add(current)
            if args.log:
                path = []
                cur = current
                while cur is not None:
                    prev, etype = parent.get(cur, (None, None))
                    if prev is not None:
                        path.append(f"{node_names[prev]} - [{edge_types[etype]}]-> {node_names[cur]}")
                    cur = prev
                path.reverse()
                logging.debug(f"\nPath to {node_names[current]}:\n  " + "\n  ".join(path))
        for kind, target, etype in adjacency.get(current, ()):
            for neighbour in (groups[target] if kind else (target,)):
                if neighbour not in visited:
                    visited.add(neighbour)
                    parent[neighbour] = (current, etype)
                    queue.append(neighbour)

    for r in reachable:
        print(node_names[r])


if __name__ == "__main__":
    main()
