#!/usr/bin/env python3
"""
Exhaustive check of every PLATFORM_EXCLUDED declaration: if a Linux .so in the
same image exports the declaration's exact Java_ symbol, the exclusion is wrong
(the method is callable on Linux). Writes out/platform_exclusion_errors.csv.
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audit_native_mapping import defined_symbols, expected_jni_symbol  # noqa: E402
from collect_sample_evidence import OUT, all_libs, app_dirs  # noqa: E402


def main():
    dirs = app_dirs()
    with open(os.path.join(OUT, "per_method.csv")) as f:
        rows = [r for r in csv.DictReader(f) if r["et_tag"] == "PLATFORM_EXCLUDED"]
    bad = []
    for r in rows:
        sym = expected_jni_symbol(r["method"])
        hits = [os.path.basename(p) for p in all_libs(dirs[r["app"]])
                if any(s == sym or s.startswith(sym + "__") for s in defined_symbols(p))]
        if hits:
            bad.append(dict(app=r["app"], method=r["method"], exclusion_rule=r["et_symbol"],
                            exported_by=" ".join(sorted(set(hits)))))
    with open(os.path.join(OUT, "platform_exclusion_errors.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["app", "method", "exclusion_rule", "exported_by"])
        w.writeheader()
        w.writerows(bad)
    print("platform exclusions: %d, exported on Linux: %d" % (len(rows), len(bad)))
    for b in bad:
        print(" ", b["app"], b["method"], "->", b["exported_by"])


if __name__ == "__main__":
    main()
