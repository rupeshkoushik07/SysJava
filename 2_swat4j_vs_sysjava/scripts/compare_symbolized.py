#!/usr/bin/env python3
"""Compare SysPart results before and after symbol restoration.

For every ELF analysed under Final_results_echotrace/<target>/Binary_Analysis/
this reads the original run and the matching Binary_Analysis_symbolized/ run
and reports functions, unnamed (fuzzyfunc-0x...) functions and syscalls, plus
which modules the remaining unnamed functions belong to.

Usage:
  python3 scripts/compare_symbolized.py [target ...]
  RESULTS_ROOT=<dir> python3 scripts/compare_symbolized.py ...   # other results tree

Writes Final_results_echotrace/symbolized_comparison.tsv and prints totals.
"""

from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path

RESULTS_ROOT = Path(os.environ.get("RESULTS_ROOT",
                                   Path(__file__).resolve().parent.parent / "Final_results_echotrace"))


def summarize(directory: Path) -> tuple[int, int, int, Counter]:
    functions = fuzzy = syscalls = 0
    modules: Counter = Counter()
    allfunctions = directory / "allfunctions.txt"
    if allfunctions.is_file():
        for line in allfunctions.read_text(errors="replace").splitlines():
            functions += 1
            if line.startswith("fuzzyfunc"):
                fuzzy += 1
                parts = line.split()
                module = parts[2] if len(parts) > 2 else "?"
                modules[Path(module.removeprefix("module-")).name or module] += 1
    syscall_file = directory / "syscalls.txt"
    if syscall_file.is_file():
        syscalls = sum(1 for line in syscall_file.read_text(errors="replace").splitlines() if line.strip())
    return functions, fuzzy, syscalls, modules


def main(argv: list[str]) -> int:
    targets = argv or sorted(p.name for p in RESULTS_ROOT.iterdir() if (p / "Binary_Analysis").is_dir())
    rows = []
    totals = Counter()
    for target in targets:
        for before in sorted((RESULTS_ROOT / target / "Binary_Analysis").glob("*/*/")):
            kind, name = before.parent.name, before.name
            after = RESULTS_ROOT / target / "Binary_Analysis_symbolized" / kind / name
            b_funcs, b_fuzzy, b_sys, _ = summarize(before)
            a_funcs, a_fuzzy, a_sys, modules = summarize(after)
            ran = (after / "allfunctions.txt").is_file()
            left = "; ".join(f"{m}={c}" for m, c in modules.most_common(4))
            rows.append((target, "binary" if kind.startswith("syscalls_BIN_") else "library", name,
                         b_funcs, b_fuzzy, b_sys, a_funcs if ran else "", a_fuzzy if ran else "",
                         a_sys if ran else "", left))
            totals["elfs"] += 1
            totals["before_functions"] += b_funcs
            totals["before_fuzzy"] += b_fuzzy
            if ran:
                totals["rerun"] += 1
                totals["after_functions"] += a_funcs
                totals["after_fuzzy"] += a_fuzzy
                totals["before_empty_now_ok"] += int(b_funcs == 0 and a_funcs > 0)
    out = RESULTS_ROOT / "symbolized_comparison.tsv"
    header = ("target", "kind", "elf", "functions_before", "fuzzy_before", "syscalls_before",
              "functions_after", "fuzzy_after", "syscalls_after", "remaining_fuzzy_by_module")
    with out.open("w") as handle:
        handle.write("\t".join(header) + "\n")
        for row in rows:
            handle.write("\t".join(str(cell) for cell in row) + "\n")
    print(", ".join(f"{k}={v}" for k, v in totals.items()))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
