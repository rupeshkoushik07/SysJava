#!/usr/bin/env python3
"""Low-memory drop-in for SysPartCode's parse_callgraph_to_json.py.

The original keeps one dict per edge holding a fresh copy of the callee's name.
A complete libjvm call graph has tens of millions of indirect edges, which
pushed the converter past 28-37 GB and killed the run (MemoryError). This
version interns every function to an integer once and stores each callsite's
edges in a packed array of 64-bit integers, so memory scales with 8 bytes per
edge. The JSON it writes is byte-for-byte the same as the original's.

Usage (same as the original):
  syspart ... -a 23 | python3 parse_callgraph_to_json_lowmem.py - out.json
"""

import json
import sys
from array import array

TYPE_BITS = 4  # edge types are a handful of short strings (DIRECT, INDIRECT, ...)


def stream_callgraph_to_json_per_callsite(output_filepath, input_stream, min_group_occurrences=2):
    func_index = {}   # name -> int (insertion order == original func_N numbering)
    func_names = []
    func_meta = []    # (module, addr) of first sighting, as in the original
    edge_types = {}
    edge_type_names = []
    callsites = {}    # (caller_int, callsite) -> array('Q') of callee_int << TYPE_BITS | type

    def intern(fn, mod, addr):
        index = func_index.get(fn)
        if index is None:
            index = len(func_names)
            func_index[fn] = index
            func_names.append(fn)
            func_meta.append((mod, addr))
        return index

    for line in input_stream:
        parts = line.split()
        if len(parts) < 8:
            if line.strip():
                print(f"Skipping malformed line: {line.strip()}", file=sys.stderr)
            continue
        edge_type, caller_module, callsite, caller_fn, callee_addr, callee_fn, callee_module, caller_addr = parts[:8]
        caller = intern(caller_fn, caller_module, caller_addr)
        callee = intern(callee_fn, callee_module, callee_addr)
        type_id = edge_types.get(edge_type)
        if type_id is None:
            type_id = edge_types[edge_type] = len(edge_type_names)
            edge_type_names.append(edge_type)
        key = (caller, sys.intern(callsite))
        edges = callsites.get(key)
        if edges is None:
            edges = callsites[key] = array("Q")
        edges.append(callee << TYPE_BITS | type_id)

    mask = (1 << TYPE_BITS) - 1

    def callee_set(edges):
        # The original keys groups by the sorted callee *names*.
        return tuple(sorted((e >> TYPE_BITS for e in edges), key=func_names.__getitem__))

    set_counts = {}
    for edges in callsites.values():
        key = callee_set(edges)
        set_counts[key] = set_counts.get(key, 0) + 1

    group_of = {}
    groups = []
    for key, count in set_counts.items():
        if count >= min_group_occurrences and len(key) > 1:
            group_of[key] = f"group_{len(groups) + 1}"
            groups.append(key)
    del set_counts

    def fid(index):
        return f"func_{index + 1}"

    with open(output_filepath, "w") as f:
        f.write("{\n")
        f.write('  "functions": [\n')
        # The original sorts its records by the "func_N" id *string*.
        order = sorted(range(len(func_names)), key=fid)
        for i, index in enumerate(order):
            module, addr = func_meta[index]
            info = {"id": fid(index), "name": func_names[index], "module": module, "addr": addr}
            f.write(f"    {json.dumps(info)}")
            f.write(",\n" if i < len(order) - 1 else "\n")
        f.write("  ],\n")

        f.write('  "callee_groups": {\n')
        for i, key in enumerate(groups):
            f.write(f'    "group_{i + 1}": {json.dumps([fid(c) for c in key])}')
            f.write(",\n" if i < len(groups) - 1 else "\n")
        f.write("  },\n")

        f.write('  "call_graph": [\n')
        total = 0
        for edges in callsites.values():
            total += 1 if callee_set(edges) in group_of else len(edges)
        written = 0
        for (caller, callsite), edges in callsites.items():
            group = group_of.get(callee_set(edges))
            if group is not None:
                edge_obj = {"caller_id": fid(caller), "callee_type": "group", "callee_ref": group,
                            "edge_type": edge_type_names[edges[0] & mask], "callsite": callsite}
                f.write(f"    {json.dumps(edge_obj)}")
                written += 1
                f.write(",\n" if written < total else "\n")
            else:
                for e in edges:
                    edge_obj = {"caller_id": fid(caller), "callee_type": "individual",
                                "callee_id": fid(e >> TYPE_BITS), "edge_type": edge_type_names[e & mask],
                                "callsite": callsite}
                    f.write(f"    {json.dumps(edge_obj)}")
                    written += 1
                    f.write(",\n" if written < total else "\n")
        f.write("  ]\n")
        f.write("}\n")
    print(f"Call graph saved to {output_filepath}", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input_file_or_dash> <output_json>", file=sys.stderr)
        sys.exit(1)
    if sys.argv[1] == "-":
        stream_callgraph_to_json_per_callsite(sys.argv[2], sys.stdin)
    else:
        with open(sys.argv[1]) as handle:
            stream_callgraph_to_json_per_callsite(sys.argv[2], handle)
