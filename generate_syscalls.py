#!/usr/bin/env python3
"""Generate an image's syscalls from its shipped dataset, without running SysPart:
the syscalls of every library and executable, the four syscall sets of the paper's
table, and the seccomp profile.

    python3 generate_syscalls.py zookeeper_3.9.5        one image (any folder name in results/)
    python3 generate_syscalls.py all                    every image with a shipped dataset

Steps:
  1. unpack the dataset: the JARs, native libraries, executables and Java runtime
     the original run copied out of the container (results/<image>/dataset/)
  2. bytecode analysis: every native method, and the JNI, JNA, JNR-FFI and FFM
     bindings (echotrace/, built with Maven on first use)
  3. mapping: each native method to the C function and library implementing it,
     which gives the start functions per library
  4. call graphs: follow SysPart's shipped call graph of each library and executable
     from those start functions to the reachable syscalls
  5. syscall sets and profile: Java libraries, executables, runtime set and
     fallback libraries, merged into the seccomp profile
  6. compare the profile with the shipped one

Output in <table folder>/generated_syscalls/<image>/:
  native_methods.txt, mapped_method_syscalls.txt   steps 2 and 3
  syscalls_output_<image>/<lib>/syscalls.txt        per library (and _BIN_ per executable,
                                                    _unanalysed_ per fallback library,
                                                    jna_ffi_analysis/ per JNA/FFI library)
  .../library_syscalls.txt, binary_syscalls.txt, unanalysed_syscalls.txt   the sets
  <image>.json      the seccomp profile
  diff.txt          against the shipped profile
  report.tsv        one line per call graph
Work files and logs: work/static/<image>/.
Needs JDK 17+, Maven, Python 3, binutils and xz.
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ART = Path(__file__).resolve().parent
TABLES = [(ART / "1_latest_containers", "results"), (ART / "2_swat4j_vs_sysjava", "sysjava_results")]


def run(cmd, log, cwd=None, env=None, check=True):
    with open(log, "w") as fh:
        rc = subprocess.run(cmd, cwd=cwd, env=env, stdout=fh, stderr=subprocess.STDOUT,
                            shell=isinstance(cmd, str)).returncode
    if rc and check:
        sys.exit(f"failed (exit {rc}); last lines of {log}:\n" + "".join(open(log).readlines()[-20:]))
    return rc


def names(profile):
    return {n for r in json.load(open(profile))["syscalls"] for n in r["names"]}


def count(path, pattern):
    return sum(1 for p in Path(path).rglob(pattern) if p.is_file()) if Path(path).is_dir() else 0


def nlines(path):
    return sum(1 for l in open(path) if l.strip()) if Path(path).is_file() else 0


def detector(shipped):
    """The detector build the shipped result was analysed with: echotrace/ or echotrace_<commit>/."""
    used = ""
    dc = shipped / "detector_commit.txt"
    if dc.is_file():
        m = re.search(r"stage4_detector_commit=([0-9a-f]+)", dc.read_text())
        used = m.group(1) if m else ""
    if not used and (shipped / "pipeline_run.log").is_file():
        m = re.findall(r"JNADetector, code at ([0-9a-f]+)", (shipped / "pipeline_run.log").read_text(errors="replace"))
        used = m[-1] if m else ""
    et = ART / "echotrace"
    if used and not (et / "COMMIT").read_text().startswith(used) and (ART / f"echotrace_{used}").is_dir():
        et = ART / f"echotrace_{used}"
    if not (et / "target" / ".classpath").is_file():
        print(f"      building {et.name} with Maven (once)")
        run("mvn -q -DskipTests compile && mvn -q dependency:build-classpath -Dmdep.outputFile=target/.classpath",
            ART / "work" / f"build_{et.name}.log", cwd=et)
    return et


def whitelist(img):
    table, sub = next(((t, s) for t, s in TABLES if (t / s / img / "Binary_Analysis").is_dir()), (None, None))
    if table is None:
        sys.exit(f"no results for {img}")
    shipped = table / sub / img
    parts = sorted(glob.glob(str(shipped / "dataset" / "Dataset.tar.xz.part*")))
    if not parts:
        sys.exit(f"{img}: no shipped dataset")
    ws = ART / "work" / "static" / img
    out = table / "generated_syscalls" / img
    shutil.rmtree(ws, ignore_errors=True)
    shutil.rmtree(out, ignore_errors=True)
    ws.mkdir(parents=True)
    out.mkdir(parents=True)
    t0 = time.time()
    step = lambda n, text: print(f"[{time.strftime('%H:%M:%S')}] {img} {n}. {text}", flush=True)

    jars, libs, bins, rt, outs = (ws / f"{d}_{img}" for d in ("JARFILES", "LIBS", "BINARIES", "RUNTIME", "outputs"))
    env = dict(os.environ, IMG_NAME=img, JARFILES_DIR=str(jars), LIBS_DIR=str(libs), BINARIES_DIR=str(bins),
               RUNTIME_DIR=str(rt), OUTPUTS_DIR=str(outs), JARFILES_IMAGE=str(jars), LIBS_IMAGE=str(libs))
    shutil.copytree(table / "scripts", ws / "scripts")
    shutil.copytree(shipped / "Dynamic_Analysis" / f"sysdig_outputs_{img}", ws / f"sysdig_outputs_{img}")
    with open(ws / "runc.txt", "w") as fh:
        if (shipped / "runtime_set.txt").is_file():
            fh.write((shipped / "runtime_set.txt").read_text())
        else:
            fh.write((table / "runc.txt").read_text())
            extra = table / "runc_host_1.3.4_additions.txt"
            if extra.is_file():
                fh.write(extra.read_text())

    step(1, f"unpack the dataset ({len(parts)} parts)")
    run("cat " + " ".join(f"'{p}'" for p in parts) + f" | xz -dc | tar -x -C '{ws}'", ws / "unpack.log")
    for d in (ws / "Dataset").iterdir():
        d.rename(ws / d.name)
    (ws / "Dataset").rmdir()
    deps = ws / "Dataset_symbolized" / f"LIBS_{img}" / "_container_deps"
    if deps.is_dir():   # libraries a copied library needs, added from the container by the original run
        for f in deps.iterdir():
            if not (libs / f.name).exists():
                shutil.copy2(f, libs / f.name)
    shutil.rmtree(ws / "Dataset_symbolized", ignore_errors=True)
    run(["bash", "scripts/relink_sonames.sh", str(libs)], ws / "relink.log", cwd=ws)
    print(f"      {count(jars, '*.jar')} JARs, {count(libs, '*.so*')} libraries, {count(bins, '*')} executables")

    et = detector(shipped)
    step(2, f"bytecode analysis ({et.name}, commit {(et / 'COMMIT').read_text()[:7]})")
    outs.mkdir()
    cp = f"{et}/target/classes:" + (et / "target" / ".classpath").read_text().strip()
    run(["java", "-Xmx16g", "-cp", cp, "com.echotrace.app.bytecode_new.JNADetector", str(jars), str(outs), str(rt)],
        ws / "bytecode.log")
    hits = lambda f: sum(1 for l in open(outs / f) if " | " in l and not l.startswith("Format:")) if (outs / f).is_file() else 0
    print(f"      {nlines(outs / 'native_methods.txt')} native methods "
          f"(shipped: {nlines(shipped / 'Bytecode_Analysis' / f'outputs_{img}' / 'native_methods.txt')}); "
          f"{hits('jna_hits.txt')} JNA, {hits('jnr_ffi_hits.txt')} JNR-FFI, {hits('ffi_hits.txt')} FFM bindings")

    step(3, "map native methods to C functions (start functions per library)")
    run(["bash", "scripts/prepare_native_mapping.sh"], ws / "mapping.log", cwd=ws, env=env)
    run([sys.executable, "scripts/analyse_jna_ffi.py", "--libs-dir", str(libs), "--outputs-dir", str(outs)],
        ws / "jna_ffi.log", cwd=ws, env=env, check=False)
    tags = re.findall(r"\[([A-Z_]+)\]$", (outs / "mapped_method_syscalls.txt").read_text(), re.M)
    print(f"      {len(tags)} native methods mapped ("
          + ", ".join(f"{t} {tags.count(t)}" for t in sorted(set(tags), key=lambda t: -tags.count(t)))
          + f"); {count(outs, '*.so*.txt')} libraries with start functions")

    step(4, "syscalls from SysPart's shipped call graphs")
    run([sys.executable, str(ART / "tools" / "whitelist_from_callgraphs.py"), img, str(shipped / "Binary_Analysis"),
         str(ws)], ws / "callgraphs.log")
    # (per-library notes on start functions the original SysPart run also skipped stay in the log)
    print("      " + "\n      ".join(l.strip() for l in open(ws / "callgraphs.log")
                                     if l.startswith(("call-graph replay", "  "))))
    shutil.copy(ws / "static_report.tsv", out / "report.tsv")

    step(5, "syscall sets and seccomp profile")
    run([sys.executable, "scripts/merge_all_syscalls.py", img], ws / "merge.log", cwd=ws, env=env, check=False)
    prof = ws / f"syscalls_output_{img}" / f"{img}.json"
    if not prof.is_file():
        sys.exit(f"no profile written; see {ws / 'merge.log'}")
    for f in ("native_methods.txt", "mapped_method_syscalls.txt"):
        shutil.copy(outs / f, out / f)
    for top in (f"syscalls_output_{img}", f"syscalls_BIN_{img}", f"syscalls_unanalysed_{img}", "jna_ffi_analysis"):
        for f in (ws / top).rglob("*syscalls.txt") if (ws / top).is_dir() else []:
            if f.name in ("syscalls.txt", "library_syscalls.txt", "binary_syscalls.txt",
                          "unanalysed_syscalls.txt", "union_syscalls.txt"):
                (out / f.relative_to(ws)).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(f, out / f.relative_to(ws))
    shutil.copy(prof, out / f"{img}.json")
    rd = lambda p: {l.strip() for l in open(ws / p) if l.strip()} if (ws / p).is_file() else set()
    lib = rd(f"syscalls_output_{img}/library_syscalls.txt") | rd("jna_ffi_analysis/union_syscalls.txt")
    binary = rd(f"syscalls_BIN_{img}/binary_syscalls.txt")
    runtime = rd("runc.txt") - lib - binary
    fallback = rd(f"syscalls_unanalysed_{img}/unanalysed_syscalls.txt") - lib - binary - runtime
    print(f"      Java libraries {len(lib)}, executables {len(binary)}, runtime set +{len(runtime)}, "
          f"fallback libraries +{len(fallback)}; profile {len(names(prof))}")

    step(6, "compare with the shipped profile")
    new, ref = names(prof), names(shipped / "Binary_Analysis" / f"syscalls_output_{img}" / f"{img}.json")
    diff = (f"generated: {len(new)} syscalls  ({out / f'{img}.json'})\n"
            f"shipped:   {len(ref)} syscalls\n"
            f"only in generated: {' '.join(sorted(new - ref))}\n"
            f"only in shipped:   {' '.join(sorted(ref - new))}\n")
    (out / "diff.txt").write_text(diff)
    print("      " + diff.strip().replace("\n", "\n      "))
    print(f"RESULT {img}: " + ("identical to the shipped profile" if new == ref else
                               f"differs from the shipped profile (see {out / 'report.tsv'})")
          + f"  [{(time.time() - t0) / 60:.0f} min]")
    return new == ref


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        sys.exit(__doc__)
    imgs = sys.argv[1:]
    if imgs == ["all"]:
        imgs = sorted(p.parent.parent.name for t, s in TABLES for p in (t / s).glob("*/dataset/Dataset.tar.xz.part00"))
    for img in imgs:
        whitelist(img)


if __name__ == "__main__":
    main()
