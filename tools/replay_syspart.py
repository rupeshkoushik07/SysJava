#!/usr/bin/env python3
"""Compute reachable syscalls from a shipped SysPart result, without SysPart.

SysPart (scripts/compute_syscalls_lowmem.sh) writes, per analysed ELF:

  allfunctions.txt               every function with its address        (-a 25)
  syscalls_with_callsites.txt    every function that issues a syscall   (-a 24)
  syscalls_cancel_sites.txt      glibc >= 2.41 cancellable sites (optional)
  callgraph.json                 call graph from the start functions    (-a 23)
  excluded_starts_syspart_crash.txt  starts dropped because SysPart crashed

and then runs getsyscalls_lowmem.py, a breadth-first search from the start
functions over that call graph. This script repeats the last step from the
shipped files for a given start-function file: it resolves versioned names
(name@@VERSION) and drops crashing starts exactly as compute_syscalls_lowmem.sh
does, then calls the same getsyscalls_lowmem.py.

The call graph only holds functions reachable from the starts SysPart was run
with. A start that is not in it (because a rerun of the bytecode analysis found
a new one) cannot be followed; it is listed in replay_missing_starts.txt and the
exit code is 2. Such a library needs the full pipeline (SysPart).

Usage:
  replay_syspart.py <shipped result dir> <start-function file> <output dir> [--log]
Files may be gzipped (callgraph.json.gz, allfunctions.txt.gz). allfunctions.txt is
optional: without it, names and addresses come from the call graph.
"""

import gzip
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# The same getsyscalls_lowmem.py the pipeline runs (identical in both table folders).
GETSYSCALLS = Path(__file__).resolve().parent.parent / "1_latest_containers" / "scripts" / "getsyscalls_lowmem.py"


def open_any(path: Path):
    gz = path.with_name(path.name + ".gz")
    if path.is_file():
        return path.open(errors="replace")
    if gz.is_file():
        return gzip.open(gz, "rt", errors="replace")
    raise FileNotFoundError(path)


def exists_any(path: Path) -> bool:
    return path.is_file() or path.with_name(path.name + ".gz").is_file()


def main():
    args = [a for a in sys.argv[1:] if a != "--log"]
    log = "--log" in sys.argv[1:]
    if len(args) != 3:
        sys.exit(__doc__)
    src, startfile, out = Path(args[0]), Path(args[1]), Path(args[2])
    out.mkdir(parents=True, exist_ok=True)

    # The call graph lists every function reachable from the starts, with its
    # address; that is all the start resolution needs. allfunctions.txt (every
    # function of the ELF) is used instead when it is shipped and not empty.
    callgraph = src / "callgraph.json"
    if not callgraph.is_file():
        tmp = out / "callgraph.json"
        with open_any(callgraph) as fin, tmp.open("w") as fout:
            shutil.copyfileobj(fin, fout)
        callgraph = tmp
    with callgraph.open() as fh:
        functions = [(f["name"], f["addr"]) for f in json.load(fh)["functions"]]
    graph_names = {f"{n}_{a}" for n, a in functions}

    addr, versioned = {}, {}
    def add(name, a):
        addr.setdefault(name, a)
        if "@" in name:
            versioned.setdefault(name.split("@", 1)[0], name)
    allfunctions = src / "allfunctions.txt"
    if exists_any(allfunctions) and not os.environ.get("REPLAY_GRAPH_ONLY"):
        with open_any(allfunctions) as fh:
            for line in fh:
                parts = line.split()
                if len(parts) >= 2:
                    add(parts[0], parts[1])
    have_allfunctions = bool(addr)
    if not addr:
        for n, a in functions:
            add(n, a)
        # A start that only issues syscalls itself has no call edges; its name
        # and address are in the syscall-site list.
        for name in ("syscalls_with_callsites.txt", "syscalls_cancel_sites.txt"):
            if exists_any(src / name):
                with open_any(src / name) as fh:
                    for line in fh:
                        parts = line.split()
                        if len(parts) >= 5:
                            add(parts[0], parts[1])
                            graph_names.add(f"{parts[0]}_{parts[1]}")

    starts = [l.split()[0] for l in startfile.read_text(errors="replace").splitlines() if l.strip()]
    resolved = [s if s in addr or s not in versioned else versioned[s] for s in starts]
    excluded_file = src / "excluded_starts_syspart_crash.txt"
    if excluded_file.is_file():
        excluded = {l.split("\t")[0] for l in excluded_file.read_text().splitlines() if l.strip()}
        resolved = [s for s in resolved if s not in excluded]
        shutil.copy(excluded_file, out / excluded_file.name)

    with_addr, missing = [], []
    for s in resolved:
        a = addr.get(s)
        if a is None:
            # With allfunctions.txt: unknown to SysPart, skipped as by
            # compute_syscalls_lowmem.sh. Without it: either that, or a start
            # the shipped call graph was not built from.
            if not have_allfunctions:
                missing.append(s)
            continue
        key = f"{s}_{a}"
        with_addr.append(key)
        if key not in graph_names:
            missing.append(s)
    (out / "startfuncs_with_addr.txt").write_text("".join(k + "\n" for k in with_addr))
    (out / "replay_missing_starts.txt").write_text("".join(s + "\n" for s in missing))

    sites = out / "syscalls_with_callsites_all.txt"
    if (src / "syscalls_with_callsites_all.txt").is_file():
        shutil.copy(src / "syscalls_with_callsites_all.txt", sites)
    else:
        with sites.open("w") as fout:
            for name in ("syscalls_with_callsites.txt", "syscalls_cancel_sites.txt"):
                if exists_any(src / name):
                    with open_any(src / name) as fin:
                        shutil.copyfileobj(fin, fout)

    cmd = [sys.executable, str(GETSYSCALLS), str(callgraph), str(sites),
           str(out / "startfuncs_with_addr.txt")]
    if log:
        cmd += ["--log", str(out / "logfile.txt")]
    with (out / "syscalls.txt").open("w") as fh:
        subprocess.run(cmd, stdout=fh, check=True)
    if callgraph.parent == out:
        callgraph.unlink()
    if missing:
        print(f"replay_syspart: {len(missing)} start function(s) not in the shipped call graph "
              f"of {src.name}; see {out / 'replay_missing_starts.txt'}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
