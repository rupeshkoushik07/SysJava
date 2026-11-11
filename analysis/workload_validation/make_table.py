#!/usr/bin/env python3
"""Per-application workload validation table from results/<app>/<mode>_<rep>.json -> results/table.md.

PASS: in every repetition the app is ready, enforce completes the same number of operations as base
with 0 failures, and the log run records no syscall outside the profile.
"""
import glob, json, os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.environ.get("WLV_RESULTS", "results")   # results folder (relative to this script)
R = defaultdict(dict)
for f in glob.glob(f"{HERE}/{RES}/*/*.json"):
    d = json.load(open(f))
    R[os.path.basename(os.path.dirname(f))][(d["mode"], d["rep"])] = d

out = ["| Application | Workload ops per run | Base: ok / failed | Log: ok / failed | Enforce: ok / failed | "
       "Would be blocked (log mode) | Runs | Result |", "|---|---:|---|---|---|---|---:|---|"]
for app in sorted(R):
    runs = R[app]
    reps = sorted({r for _, r in runs})
    def agg(mode):
        rs = [runs[(mode, r)] for r in reps if (mode, r) in runs]
        return sum(x["ops_ok"] for x in rs), sum(x["ops_failed"] for x in rs), rs
    (bo, bf, br), (lo, lf, lr), (eo, ef, er) = agg("base"), agg("log"), agg("enforce")
    denied = sorted({s for x in lr for s in x["would_be_denied"]})
    ok = (all(x["ready"] for x in br + lr + er) and len(br) == len(lr) == len(er) == len(reps)
          and bf == lf == ef == 0 and bo == lo == eo and bo > 0 and not denied)
    per_run = bo // len(br) if br else 0
    out.append(f"| {app} | {per_run:,} | {bo:,} / {bf} | {lo:,} / {lf} | {eo:,} / {ef} | "
               f"{', '.join(denied) or 'none'} | {len(runs)} | "
               f"{'PASS' if ok else 'FAIL'} |")
open(f"{HERE}/{RES}/table.md", "w").write("\n".join(out) + "\n")
print("\n".join(out))
