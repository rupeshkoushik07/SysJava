#!/usr/bin/env python3
"""Recall of stage 4's native-method list against natives called at runtime.

Ground truth comes from scripts/native_recall_capture.sh: the JVM's
-verbose:jni log. Only "[Dynamic-linking native method C.m ...]" lines count,
because HotSpot prints them the first time a native is actually called;
"[Registering JNI native method ...]" lines list whole RegisterNatives tables
whether or not each entry is ever called.

Usage:
  python3 scripts/native_recall_compare.py <label>=<dir-with-<target>/native_methods.txt> [...]
  e.g. before=Final_results_JDK8/_before_clinit_fix after=Final_results_JDK8/_after_clinit_fix

Prints per-target recall for each labelled list and the natives every list
still misses, split into init-style natives (initIDs, registerNatives, init:
called from static initializers) and the rest.
"""

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "Final_results_JDK8" / "_native_recall"
INIT_STYLE = re.compile(r"\.(initIDs|registerNatives|init|initNative|initialize)$")


def called(target: str) -> set[str]:
    log = (ROOT / target / "jni.log").read_text(errors="ignore")
    return set(re.findall(r"\[Dynamic-linking native method (\S+)", log))


def main(argv: list[str]) -> int:
    lists = [arg.split("=", 1) for arg in argv]
    targets = sorted(p.name for p in ROOT.iterdir() if (p / "jni.log").is_file())
    header = f"{'target':32} {'called':>6}" + "".join(f" {label + ' found':>14} {'recall':>6}" for label, _ in lists)
    print(header)
    totals = Counter()
    still_missed = Counter()
    for target in targets:
        runtime = called(target)
        totals["called"] += len(runtime)
        row = f"{target:32} {len(runtime):>6}"
        missed_by_all = set(runtime)
        for label, directory in lists:
            path = Path(directory) / target / "native_methods.txt"
            if not path.is_file():
                row += f" {'-':>14} {'-':>6}"
                continue
            static = set(path.read_text().split())
            found = runtime & static
            totals[label] += len(found)
            totals[label + "_called"] += len(runtime)
            missed_by_all -= found
            row += f" {len(found):>14} {len(found) / len(runtime):>6.0%}"
        still_missed.update(missed_by_all)
        print(row)
    print()
    for label, _ in lists:
        if totals[label + "_called"]:
            print(f"{label}: {totals[label]}/{totals[label + '_called']} called natives found "
                  f"({totals[label] / totals[label + '_called']:.0%})")
    init = sorted(m for m in still_missed if INIT_STYLE.search(m))
    rest = sorted(((c, m) for m, c in still_missed.items() if not INIT_STYLE.search(m)), reverse=True)
    print(f"\nmissed by every list: {len(still_missed)} distinct "
          f"({len(init)} init-style, {len(rest)} other)")
    for m in init:
        print(f"  init  {still_missed[m]}  {m}")
    for c, m in rest[:30]:
        print(f"  other {c}  {m}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
