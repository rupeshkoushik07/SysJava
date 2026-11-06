#!/usr/bin/env python3
"""AUTHOR-SIDE: remove from <table>/scripts/ every script the pipeline never calls.

A script is kept when its name appears in the table's driver, or in any script outside
the scripts/ folders (reproduce.sh, generate_syscalls.py, setup.sh, tools/, analysis/,
swat4j/), or in a script kept that way. One-off rerun and debugging helpers used while
producing the results are not called by any of these and are dropped.

Usage: prune_scripts.py <artifact dir> <table folder> <driver name>
"""
import re
import sys
from pathlib import Path

art, table, driver = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
scripts = art / table / "scripts"
cands = {p.name: p for p in scripts.rglob("*") if p.is_file() and p.suffix in (".sh", ".py")}
roots = [scripts / driver] + [p for p in art.rglob("*") if p.is_file() and p.suffix in (".sh", ".py")
                              and "/scripts/" not in str(p.relative_to(art)) + "/"
                              and not str(p.relative_to(art)).startswith(("echotrace", "work/", "Results/"))
                              and p.name not in ("build_artifact.sh", "prune_scripts.py")]   # author-side
seen, stack = set(), list(roots)
while stack:
    p = stack.pop()
    if p in seen:
        continue
    seen.add(p)
    text = p.read_text(errors="replace")
    for name, q in cands.items():
        if q not in seen and re.search(r"(?<![\w.-])" + re.escape(name) + r"(?![\w-])", text):
            stack.append(q)
dropped = sorted(n for n, p in cands.items() if p not in seen)
for n in dropped:
    cands[n].unlink()
print(f"{table}/scripts: kept {len(cands) - len(dropped)}, removed {len(dropped)}: {' '.join(dropped)}")
