#!/usr/bin/env python3
"""Recompute every SysPart syscall set of one image from its shipped call graphs.

This replaces pipeline stages 6-8 (debug symbols and SysPart) in the static
mode. It walks the shipped Binary_Analysis/ of one image and, for every SysPart
result in it, recomputes syscalls.txt with replay_syspart.py into the same
relative path under the workspace. merge_all_syscalls.py then builds the
profile from the workspace exactly as in the full pipeline.

Start functions:
  syscalls_output_<img>/<lib>         from this rerun's native mapping
                                      (<outputs dir>/**/<lib>.txt, as stage 7)
  jna_ffi_analysis/syscalls/<lib>     from this rerun's JNA/FFI bindings
                                      (jna_ffi_analysis/startfuncs/<lib>.txt)
  syscalls_BIN_<img>/<exe>            the executable's entry point, and
  syscalls_unanalysed_<img>/<lib>     the library's exports: neither depends on
                                      the bytecode analysis, so the shipped
                                      starts are used

Reported, not hidden:
  * a library the rerun maps but the shipped results have no call graph for
    (new library), and start functions missing from a shipped call graph:
    both need the full pipeline;
  * a shipped library the rerun no longer maps: it is left out, as stage 7
    would leave it out.

Usage: whitelist_from_callgraphs.py <img> <shipped Binary_Analysis dir> <workspace>
Writes <workspace>/static_report.tsv.
"""

import shutil
import subprocess
import sys
from pathlib import Path

REPLAY = Path(__file__).resolve().parent / "replay_syspart.py"


def has_graph(d: Path) -> bool:
    return (d / "callgraph.json").is_file() or (d / "callgraph.json.gz").is_file()


def shipped_starts(d: Path, dest: Path) -> Path:
    """The start functions of a shipped result: startfuncs_with_addr.txt (name_addr), or
    startfuncs_resolved.txt (names) where SysPart wrote only that."""
    if (d / "startfuncs_with_addr.txt").is_file():
        names = [l.rsplit("_", 1)[0] for l in (d / "startfuncs_with_addr.txt").read_text().split()]
    else:
        names = (d / "startfuncs_resolved.txt").read_text().split()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("".join(n + "\n" for n in names))
    return dest


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    img, shipped, ws = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    outputs = ws / f"outputs_{img}"
    jna_starts = ws / "jna_ffi_analysis" / "startfuncs"
    report = []

    # stage 7 picks start files with find | sort; a later file with the same
    # basename overwrites an earlier one, so the last one wins here too.
    mapped = {}
    for f in sorted(str(p) for p in outputs.rglob("*.txt")):
        name = Path(f).name[:-4]
        if ".so" in name:
            mapped[name] = Path(f)

    graphs = sorted(p.parent for p in shipped.rglob("callgraph.json*"))
    kinds = {f"syscalls_output_{img}": "library", f"syscalls_BIN_{img}": "executable",
             f"syscalls_unanalysed_{img}": "fallback library", "jna_ffi_analysis": "JNA/FFI library",
             "extra_components": "extra component"}
    for i, d in enumerate(graphs, 1):
        rel = d.relative_to(shipped)
        out = ws / rel
        top = rel.parts[0]
        if top == f"syscalls_output_{img}":
            starts = mapped.pop(d.name, None)
        elif top == "jna_ffi_analysis":
            starts = jna_starts / f"{d.name}.txt"
            starts = starts if starts.is_file() else None
        elif (d / "startfuncs_with_addr.txt").is_file() or (d / "startfuncs_resolved.txt").is_file():
            starts = shipped_starts(d, ws / "static_starts" / rel / "starts.txt")
        else:
            starts = None
        if starts is None:
            print(f"[{i}/{len(graphs)}] {kinds.get(rel.parts[0], rel.parts[0])} {d.name}: not mapped in this run", flush=True)
            report.append(("not_mapped_in_rerun", str(rel), "left out"))
            continue
        code = subprocess.run([sys.executable, str(REPLAY), str(d), str(starts), str(out)]).returncode
        n = len((out / "syscalls.txt").read_text().split()) if (out / "syscalls.txt").is_file() else 0
        print(f"[{i}/{len(graphs)}] {kinds.get(rel.parts[0], rel.parts[0])} {d.name}: {n} syscalls", flush=True)
        if code == 2:
            # Starts the original run also had but SysPart did not know (not in
            # its function list) were skipped there too; only others are gaps.
            missing = set((out / "replay_missing_starts.txt").read_text().split())
            if (d / "startfuncs_resolved.txt").is_file():
                missing -= set((d / "startfuncs_resolved.txt").read_text().split())
            if (d / "startfuncs_with_addr.txt").is_file():
                missing -= {l.rsplit("_", 1)[0] for l in (d / "startfuncs_with_addr.txt").read_text().split()}
            if missing:
                report.append(("starts_not_in_callgraph", str(rel), f"{len(missing)} starts; {n} syscalls"))
            else:
                report.append(("ok", str(rel), f"{n} syscalls"))
        elif code != 0:
            report.append(("replay_failed", str(rel), f"exit {code}"))
        else:
            report.append(("ok", str(rel), f"{n} syscalls"))

    # SysPart results that failed in the original run (no call graph) keep
    # their (empty or missing) syscalls.txt, so the merge reports them the same way.
    for top in (f"syscalls_output_{img}", f"syscalls_BIN_{img}"):
        base = shipped / top
        for d in sorted(base.iterdir()) if base.is_dir() else []:
            if d.is_dir() and not has_graph(d):
                (ws / top / d.name).mkdir(parents=True, exist_ok=True)
                if (d / "syscalls.txt").is_file():
                    shutil.copy(d / "syscalls.txt", ws / top / d.name / "syscalls.txt")
                report.append(("no_callgraph_in_original", f"{top}/{d.name}", "copied as shipped"))
                mapped.pop(d.name, None)

    for name, f in sorted(mapped.items()):
        report.append(("new_library_needs_syspart", f"syscalls_output_{img}/{name}", str(f.relative_to(ws))))

    union = set()
    for f in (ws / "jna_ffi_analysis" / "syscalls").glob("*/syscalls.txt"):
        union |= set(f.read_text().split())
    if (ws / "jna_ffi_analysis").is_dir():
        (ws / "jna_ffi_analysis" / "union_syscalls.txt").write_text("".join(s + "\n" for s in sorted(union)))

    with (ws / "static_report.tsv").open("w") as fh:
        fh.write("status\tresult\tdetail\n")
        for row in report:
            fh.write("\t".join(row) + "\n")
    counts = {}
    for status, _, _ in report:
        counts[status] = counts.get(status, 0) + 1
    print("call-graph replay: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    for status, rel, detail in report:
        if status not in ("ok", "no_callgraph_in_original"):
            print(f"  {status}: {rel} ({detail})")
    return 1 if any(s in ("replay_failed",) for s, _, _ in report) else 0


if __name__ == "__main__":
    sys.exit(main())
