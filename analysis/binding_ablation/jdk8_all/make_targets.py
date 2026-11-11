#!/usr/bin/env python3
"""One no-binding (arm A) SysPart run per DISTINCT library file of the ten JDK 8 images.

Every library the pipeline analysed (sysjava_results/<t>/Binary_Analysis/syscalls_output_<t>/<lib>/) is
found in work/<t>/Dataset_symbolized/LIBS_<t> (unpack_libs.py) and hashed; identical files get one run,
in the first image that has it. The run is named after the real file (SysPart names a module by its
file, so a symlink name would match no function). libjvm.so is left out ("not resolved").

Writes targets/<img>.tsv (lib, library path, binding start list) and results/libraries.tsv.
Usage: python3 make_targets.py [work-dir]
"""
import hashlib, os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ART = HERE.parents[2]
R = ART / "2_swat4j_vs_sysjava" / "sysjava_results"
WORK = Path(sys.argv[1] if len(sys.argv) > 1 else HERE / "work").resolve()
(HERE / "targets").mkdir(exist_ok=True)
(HERE / "results").mkdir(exist_ok=True)
rep, rows, targets = {}, [], {}
for d in sorted(R.glob("*-jdk8-buster")):
    t = d.name
    out = d / "Binary_Analysis" / f"syscalls_output_{t}"
    L = WORK / t / "Dataset_symbolized" / f"LIBS_{t}"
    for lib in sorted(os.listdir(out)):
        b = out / lib
        if not b.is_dir() or not (b / "syscalls.txt").exists():
            continue
        cands = sorted((os.path.join(r, lib) for r, _, fs in os.walk(L) if lib in fs), key=len)
        if not cands:
            print("not found:", t, lib)
            continue
        path = os.path.realpath(cands[0])
        sha = hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]
        first = sha not in rep
        rep.setdefault(sha, (t, os.path.basename(path)))
        rows.append((t, lib, sha, rep[sha][0], rep[sha][1], str(b.relative_to(ART))))
        if first and lib != "libjvm.so":
            targets.setdefault(t, []).append((os.path.basename(path), path, str(b / "startfuncs_resolved.txt")))
for t, ts in targets.items():
    (HERE / "targets" / f"{t}.tsv").write_text("".join("\t".join(x) + "\n" for x in ts))
with open(HERE / "results" / "libraries.tsv", "w") as f:
    f.write("img\tlib\tsha256_16\tA_run_img\tA_run_lib\tbinding_run\n")
    f.write("".join("\t".join(r) + "\n" for r in rows))
print(len(rows), "library analyses in 10 images;", len(rep), "distinct files;",
      sum(len(v) for v in targets.values()), "no-binding runs (libjvm excluded)")
