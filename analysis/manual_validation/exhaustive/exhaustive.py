#!/usr/bin/env python3
"""Run sample.py's per-mapping check on EVERY mapping of every stratum (not a sample). Read-only.
Writes exhaustive/all.tsv (stratum, set, image, tag, java, native, library, verdict, reason) and prints counts."""
import csv, os, sys
from collections import Counter
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, H)
import sample as S   # unchanged; main() not called
pop = S.build()
c = Counter()
with open(os.path.join(H, "exhaustive", "all.tsv"), "w", newline="") as f:
    w = csv.writer(f, delimiter="\t", lineterminator="\n")
    w.writerow(["stratum", "set", "image", "tag", "java", "native", "library", "verdict", "reason"])
    for k in sorted(S.P.STRATA):
        for r in pop.get(k, []):
            try:
                _, (v, why) = S.EV[k](r)
            except Exception as e:
                v, why = "error", repr(e)[:200]
            c[(k, v)] += 1
            w.writerow([k, r["set"], r["img"], r["tag"], r["java"], r["sym"], S.rel(r["lib"]) if r["lib"] else "", v, why])
for k in sorted(S.P.STRATA):
    print(k, S.P.STRATA[k], {v: n for (kk, v), n in sorted(c.items()) if kk == k})
