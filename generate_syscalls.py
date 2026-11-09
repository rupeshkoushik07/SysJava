#!/usr/bin/env python3
"""Generate an image's syscalls from its shipped dataset and SysPart's shipped call graphs:
the syscalls of every library and executable, the four syscall sets of the paper's
table, and the seccomp profile.

    python3 generate_syscalls.py zookeeper_3.9.5        one image (any folder name in results/)
    python3 generate_syscalls.py all                    every image with a shipped dataset
    python3 generate_syscalls.py --no-run <image>       without the container run (no Docker)
    python3 generate_syscalls.py -q <image>             one summary line per stage instead

It prints what the pipeline's run prints (results/<image>/pipeline_run.log): the stage
headers of the table's driver (run_latest_target.sh, run_jdk8_target.sh) with the same
numbers, and the output of each tool as it runs. Stages 1-2 (start the container, sysdig
capture) are the shipped capture; stage 3 unpacks it, and SysPart's stages read its shipped
call graphs. Each tool's output is also in its log in work/static/<image>/.

Stages (latest images; the JDK 8 driver numbers merge 9 and the container run 10):
  3. the JARs, native libraries, executables and Java runtime the original run copied
     out of the container, unpacked from results/<image>/dataset/
  4. bytecode analysis: every native method, and the JNI, JNA, JNR-FFI and FFM
     bindings (echotrace/, built with Maven on first use)
  5. native mapping: each native method to the C function and library implementing it,
     which gives the start functions per library
  6. debug symbols are in the shipped capture already; the libraries the copied ones
     need and the SONAME links
  7-8. SysPart: from those start functions, the reachable syscalls in the shipped call
     graph of each library and executable (also the unanalysed loaded libraries and
     the JNA/FFI-bound ones)
  9. named call graphs: functions and unnamed (fuzzyfunc) functions per call graph
  10. syscall sets (Java libraries, executables, runtime set, fallback libraries)
     merged into the seccomp profile;
     then the results as the image's column of its table (Table III, or tab:results
     for the JDK 8 images): native methods by mapping kind, not found, syscall rows
  11. the container under the generated profile (tools/check_profile.sh): once
     without and once with the profile; PASS when it starts, keeps running, answers
     its probe and logs no extra "Operation not permitted". Needs Docker; skipped
     without it or with --no-run

Output in <table folder>/generated_syscalls/<image>/:
  native_methods.txt, mapped_method_syscalls.txt   stages 4 and 5
  syscalls_output_<image>/<lib>/syscalls.txt        per library (and _BIN_ per executable,
                                                    _unanalysed_ per fallback library,
                                                    jna_ffi_analysis/ per JNA/FFI library)
  .../library_syscalls.txt, binary_syscalls.txt, unanalysed_syscalls.txt   the sets
  <image>.json      the seccomp profile
  diff.txt          the profile against the shipped one (for checking a run)
  report.tsv        one line per call graph
  table_column.txt  the results as the image's column of its table
  seccomp_runtime_test.log   the last stage (RESULT=PASS or FAIL with the reasons)
Work files and logs: work/static/<image>/.
Needs JDK 17+, Maven, Python 3, binutils and xz; the container run needs Docker.
"""
import csv
import glob
import gzip
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


QUIET = False   # -q


def summary(text):
    """A stage's summary line (-q only)."""
    if QUIET:
        print(f"      {text}", flush=True)


def run(cmd, log, cwd=None, env=None, check=True, echo=True):
    """Run cmd with its output in log and, as the driver does, on the terminal (-q or not echo:
    log only)."""
    with open(log, "w") as fh:
        p = subprocess.Popen(cmd, cwd=cwd, env=dict(env or os.environ, PYTHONUNBUFFERED="1"),
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=isinstance(cmd, str),
                             text=True, errors="replace")
        for line in p.stdout:
            fh.write(line)
            if echo and not QUIET:
                print(line, end="", flush=True)
        rc = p.wait()
    if rc and check:
        sys.exit(f"failed (exit {rc}); last lines of {log}:\n" + "".join(open(log).readlines()[-20:]))
    return rc


def rel(p):
    """A path relative to the artifact folder, as printed."""
    return os.path.relpath(p, ART)


def names(profile):
    return {n for r in json.load(open(profile))["syscalls"] for n in r["names"]}


def count(path, pattern):
    return sum(1 for p in Path(path).rglob(pattern) if p.is_file()) if Path(path).is_dir() else 0


def nlines(path):
    return sum(1 for l in open(path) if l.strip()) if Path(path).is_file() else 0


REPLAY = {"ok": "{} call graphs parsed",
          "no_callgraph_in_original": "{} library/executable without a call graph in the original run either (kept as shipped)",
          "starts_not_in_callgraph": "{} missing start functions (need a SysPart run)",
          "new_library_needs_syspart": "{} libraries not in the shipped results (need a SysPart run)",
          "not_mapped_in_rerun": "{} shipped results not mapped in this run (left out)",
          "replay_failed": "{} failed"}


def replay_summary(log):
    """whitelist_from_callgraphs.py's summary line in words, plus any line it flags."""
    lines = open(log).read().splitlines()
    summary = next((l for l in lines if l.startswith("call-graph replay:")), "")
    counts = dict(kv.split("=") for kv in summary.split(":", 1)[-1].split(", ") if "=" in kv)
    order = sorted(counts, key=lambda k: list(REPLAY).index(k.strip()) if k.strip() in REPLAY else len(REPLAY))
    text = "; ".join(REPLAY.get(k.strip(), k.strip() + " {}").format(counts[k]) for k in order)
    flagged = [l.strip() for l in lines if l.startswith("  ")]
    return "\n      ".join([text] + flagged)


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
        print(f"building {et.name} with Maven (once)", flush=True)
        run("mvn -q -DskipTests compile && mvn -q dependency:build-classpath -Dmdep.outputFile=target/.classpath",
            ART / "work" / f"build_{et.name}.log", cwd=et)
    return et


def fold_manual_mappings(shipped, outs, img, table):
    """Add the manual mappings (natives whose library the image does not ship, or that the
    mapper misses) to the start files, as the run did before SysPart. JDK 8 results record them,
    with dataset paths, in outputs_<image>/manual_mapped_method_syscalls.txt
    (scripts/apply_manual_mappings.py); for the latest images they are the LIBS_<image>/ lines of
    manual_mapping/<image>/mapping/mapped_method_syscalls.txt (the RTA rerun's fold step)."""
    rec = shipped / "Bytecode_Analysis" / f"outputs_{img}" / "manual_mapped_method_syscalls.txt"
    if rec.is_file():
        shutil.copy(rec, outs / rec.name)
        by_name = False
    else:
        rec = table / "manual_mapping" / img / "mapping" / "mapped_method_syscalls.txt"
        by_name = True   # a library not at that path: the start file of the same name
        if not rec.is_file():
            return 0
    starts = {}
    for l in rec.read_text().splitlines():
        m = re.match(rf"^LIBS_{re.escape(img)}/(\S+?):[\w.$]+ -> (\S+) \[\w+\]", l)
        if m and "NOT_FOUND" not in l:
            sf = outs / f"{m.group(1)}.txt"
            lib = outs.parent / f"LIBS_{img}" / m.group(1)
            if not by_name and lib.is_symlink() and not sf.is_file():
                # as apply_manual_mappings.py: a link (libc.so.6) gets the start file of its target
                real = lib.resolve()
                if real.is_relative_to(lib.parent.resolve()):
                    sf = outs / f"{real.relative_to(outs.parent.resolve() / f'LIBS_{img}')}.txt"
            if by_name and not sf.is_file():
                sf = next(iter(sorted(outs.rglob(Path(m.group(1)).name + ".txt"))), sf)
            starts.setdefault(sf, set()).add(m.group(2))
    n = 0
    for sf, syms in starts.items():
        old = sf.read_text().split() if sf.is_file() else []
        add = sorted(syms - set(old))
        if add:
            sf.parent.mkdir(parents=True, exist_ok=True)
            sf.write_text("".join(x + "\n" for x in old + add))
            n += len(add)
    return n


# the stage numbers of the table's driver
STAGES = {"latest": dict(unpack=3, bytecode=4, mapping=5, symbols=6, syspart="7-8", named=9, merge=10, run=11),
          "jdk8": dict(unpack=3, bytecode=4, mapping=5, symbols=6, syspart="7-8", merge=9, run=10)}

def whitelist(img, run_container=True):
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
    jdk8 = table.name.startswith("2_")
    num = STAGES["jdk8" if jdk8 else "latest"]
    stage = lambda n, text: print(f"\n===== [{time.strftime('%Y-%m-%d %H:%M:%S')}] {img} stage {num.get(n, n)}: {text}",
                                  flush=True)

    jars, libs, bins, rt, outs = (ws / f"{d}_{img}" for d in ("JARFILES", "LIBS", "BINARIES", "RUNTIME", "outputs"))
    env = dict(os.environ, IMG_NAME=img, JARFILES_DIR=str(jars), LIBS_DIR=str(libs), BINARIES_DIR=str(bins),
               RUNTIME_DIR=str(rt), OUTPUTS_DIR=str(outs), JARFILES_IMAGE=str(jars), LIBS_IMAGE=str(libs))
    shutil.copytree(table / "scripts", ws / "scripts")
    shutil.copytree(shipped / "Dynamic_Analysis" / f"sysdig_outputs_{img}", ws / f"sysdig_outputs_{img}")
    if (shipped / "extra_components").is_dir():   # e.g. Elastic ML: syscalls from its imports (merged)
        shutil.copytree(shipped / "extra_components", ws / "extra_components")
    with open(ws / "runc.txt", "w") as fh:
        if (shipped / "runtime_set.txt").is_file():
            fh.write((shipped / "runtime_set.txt").read_text())
        else:
            fh.write((table / "runc.txt").read_text())
            extra = table / "runc_host_1.3.4_additions.txt"
            if extra.is_file():
                fh.write(extra.read_text())

    stage("unpack", f"extract JDK runtime, JARs, native libraries (from the shipped capture, {rel(shipped / 'dataset')}/)")
    run("cat " + " ".join(f"'{p}'" for p in parts) + f" | xz -dc | tar -x -C '{ws}'", ws / "unpack.log")
    for d in (ws / "Dataset").iterdir():
        d.rename(ws / d.name)
    (ws / "Dataset").rmdir()
    if not QUIET:
        print(f"captured: {count(jars, '*.jar')} JARs, {count(libs, '*.so*')} native libraries, "
              f"libjvm.so: {count(libs, 'libjvm.so')}", flush=True)
    summary(f"{count(jars, '*.jar')} JARs, {count(libs, '*.so*')} libraries, {count(bins, '*')} executables")

    et = detector(shipped)
    commit = (et / "COMMIT").read_text()[:7]
    stage("bytecode", "bytecode analysis (JNADetector)" if jdk8 else f"bytecode analysis (JNADetector, code at {commit} in {et})")
    outs.mkdir()
    cp = f"{et}/target/classes:" + (et / "target" / ".classpath").read_text().strip()
    run(["java", f"-Xmx{os.environ.get('ECHOTRACE_XMX', '16g')}", "-cp", cp, "com.echotrace.app.bytecode_new.JNADetector",
         str(jars), str(outs), str(rt)], ws / "bytecode.log")
    hits = lambda f: sum(1 for l in open(outs / f) if " | " in l and not l.startswith("Format:")) if (outs / f).is_file() else 0
    summary(f"{nlines(outs / 'native_methods.txt')} native methods; "
            f"{hits('jna_hits.txt')} JNA, {hits('jnr_ffi_hits.txt')} JNR-FFI, {hits('ffi_hits.txt')} FFM bindings")

    stage("mapping", "native mapping and start functions")
    run(["bash", "scripts/prepare_native_mapping.sh"], ws / "mapping.log", cwd=ws, env=env)
    if not jdk8 and (ws / "scripts" / "check_jni_overloads.py").is_file():
        # every overload of an overloaded JNI method must be mapped
        if run([sys.executable, "scripts/check_jni_overloads.py", str(libs), str(outs), str(out / "jni_overload_check.tsv")],
               ws / "overloads.log", cwd=ws, check=False):
            print(f"WARNING: overloaded JNI symbols missing from the mapping, see {out / 'jni_overload_check.tsv'}")

    stage("symbols", "debug symbols (in the shipped capture already); container dependencies and SONAME links")
    # the libraries a copied library needs (added from the container) and SONAME links
    deps = ws / "Dataset_symbolized" / f"LIBS_{img}" / "_container_deps"
    if deps.is_dir():
        for f in deps.iterdir():
            if not (libs / f.name).exists():
                shutil.copy2(f, libs / f.name)
    shutil.rmtree(ws / "Dataset_symbolized", ignore_errors=True)
    run(["bash", "scripts/relink_sonames.sh", str(libs)], ws / "relink.log", cwd=ws, echo=False)
    if (shipped / "debug_symbols.tsv").is_file() and not QUIET:
        st = [l.split("\t")[2] for l in (shipped / "debug_symbols.tsv").read_text().splitlines()[1:] if l.count("\t") >= 2]
        print(" ".join(f"{k}={st.count(k)}" for k in sorted(set(st))) + " ")

    stage("syspart", "SysPart: mapped libraries, executed binaries, unanalysed loaded libraries and JNA/FFI "
                     f"bindings (call graphs of the shipped run, {rel(shipped / 'Binary_Analysis')}/)")
    run([sys.executable, "scripts/analyse_jna_ffi.py", "--libs-dir", str(libs), "--outputs-dir", str(outs)],
        ws / "jna_ffi.log", cwd=ws, env=env, check=False)
    manual = fold_manual_mappings(shipped, outs, img, table)
    if manual and not QUIET:
        print(f"manual mappings: {manual} start functions added")
    tags = re.findall(r"\[([A-Z_]+)\]$", (outs / "mapped_method_syscalls.txt").read_text(), re.M)
    summary(f"{len(tags)} native methods mapped ("
            + ", ".join(f"{t} {tags.count(t)}" for t in sorted(set(tags), key=lambda t: -tags.count(t)))
            + f"); {count(outs, '*.so*.txt')} libraries with start functions"
            + (f"; {manual} manual mappings added" if manual else ""))

    run([sys.executable, str(ART / "tools" / "whitelist_from_callgraphs.py"), img, str(shipped / "Binary_Analysis"),
         str(ws)], ws / "callgraphs.log")
    summary(replay_summary(ws / "callgraphs.log"))
    shutil.copy(ws / "static_report.tsv", out / "report.tsv")

    if "named" in num:
        stage("named", "named call graphs: unnamed (fuzzyfunc) functions per result")
        named_callgraphs(img, shipped / "Binary_Analysis", ws, out)

    stage("merge", "merge syscalls into seccomp profile, assemble results")
    if run([sys.executable, "scripts/merge_all_syscalls.py", img], ws / "merge.log", cwd=ws, env=env, check=False) \
            and (ws / f"syscalls_output_{img}" / f"{img}.json").is_file() and not QUIET:
        print(f"stage {num['merge']}: merge reported items without results (listed above); profile written, continuing")
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
    summary(f"Java libraries {len(lib)}, executables {len(binary)}, runtime set +{len(runtime)}, "
            f"fallback libraries +{len(fallback)}; profile {len(names(prof))}")

    # diff.txt: this profile against the shipped one, for checking a run (not printed)
    new, ref = names(prof), names(shipped / "Binary_Analysis" / f"syscalls_output_{img}" / f"{img}.json")
    (out / "diff.txt").write_text(f"generated: {len(new)} syscalls\nshipped:   {len(ref)} syscalls\n"
                                  f"only in generated: {' '.join(sorted(new - ref)) or 'none'}\n"
                                  f"only in shipped:   {' '.join(sorted(ref - new)) or 'none'}\n")

    if (table / "manual_mapping").is_dir():
        stage("results", f"the image's column of {'tab:results' if jdk8 else 'Table III'} "
                         f"(written to {rel(out / 'table_column.txt')})")
        print(table_column(img, ws, table, out), flush=True)
    stage("run", "run the container under its profile")
    log = out / "seccomp_runtime_test.log"
    if not run_container:
        print("skipped (--no-run)")
    elif subprocess.run(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
        print("skipped: Docker is not available")
    else:
        run(["bash", str(ART / "tools" / "check_profile.sh"), img, str(out / f"{img}.json"), str(log)],
            ws / "check_profile.log", check=False)
        kv = dict(l.split("=", 1) for l in log.read_text().splitlines() if "=" in l and " " not in l.split("=", 1)[0]) \
            if log.is_file() else {}
        if "RESULT" not in kv:
            print(f"no result; see {ws / 'check_profile.log'}")
        else:
            summary(f"without profile: ready after {kv.get('baseline_ready_after', '?')}, "
                    f"{kv.get('baseline_state', '?')}, probe {kv.get('baseline_probe', '?')}")
            summary(f"with profile ({kv.get('profile_syscalls', '?').split()[0]} syscalls): ready after "
                    f"{kv.get('ready_after', '?')}, {kv.get('state_after_60s', '?')} after 60 s, "
                    f"probe {kv.get('probe', '?')}, EPERM lines {kv.get('eperm_lines', '?')}")
            summary(f"RESULT={kv['RESULT']}  (log: {rel(log)})")
    stage("done", f"finished in {(time.time() - t0) / 60:.0f} min; profile: {out / f'{img}.json'}")


def named_callgraphs(img, shipped, ws, out):
    """Stage 9 of the latest driver: functions and unnamed (fuzzyfunc) functions of each call
    graph (the shipped one) and the syscalls found from it (this run)."""
    rows = []
    for top in (f"syscalls_output_{img}", f"syscalls_BIN_{img}"):
        for d in sorted((shipped / top).iterdir()) if (shipped / top).is_dir() else []:
            af = d / "allfunctions.txt.gz"
            if not af.is_file():
                continue
            funcs = gzip.open(af, "rt", errors="replace").read().splitlines()
            sc = ws / top / d.name / "syscalls.txt"
            rows.append(f"{d.name}\tfunctions={len(funcs)}\tfuzzy={sum(1 for f in funcs if f.startswith('fuzzyfunc'))}"
                        f"\tsyscalls={nlines(sc) if sc.is_file() else 0}")
    (out / "named_callgraph_summary.tsv").write_text("".join(r + "\n" for r in rows))
    if not QUIET:
        print("\n".join(rows), flush=True)


def tex_column(tex, img):
    """(label, value) rows of one image's column in a table .tex file."""
    lines = Path(tex).read_text().splitlines()
    head = next(l for l in lines if l.lstrip().startswith("&") and "Zookeeper" in l)
    col = [c.strip().lower() for c in head.rstrip("\\ ").split("&")[1:]].index(img.split("_")[0]) + 1
    rows = []
    for l in lines[lines.index(head) + 1:]:
        cells = [c.strip() for c in l.rstrip("\\ ").split("&")]
        if len(cells) > col and cells[0] and (cells[0].startswith("\\quad") or not cells[0].startswith(("\\", "%"))):
            label = re.sub(r"\\quad\s*", "  ", cells[0]).replace("\\_", "_").replace("\\$", "$")
            for tex, sym in (("$\\Delta$", "Δ"), ("$\\cup$", "∪"), ("$\\cap$", "∩")):
                label = label.replace(tex, sym)
            rows.append((label, cells[col]))
        elif "multicolumn" in l:
            rows.append((re.search(r"\}\{([^{}]*)\}\s*\\\\", l).group(1), None))
    return rows


def table_column(img, ws, table, out):
    """Run the mapping audit and the table generator on this run's files and return the
    image's column."""
    jdk8 = table.name.startswith("2_")
    sub = "sysjava_results" if jdk8 else "results"
    shipped = table / sub / img
    tv = ws / "table_view"
    shutil.rmtree(tv, ignore_errors=True)
    v = tv / img
    for d in ("Bytecode_Analysis", "Binary_Analysis", "Dataset"):
        (v / d).mkdir(parents=True)
    (v / "Bytecode_Analysis" / f"outputs_{img}").symlink_to(ws / f"outputs_{img}")
    for d in (f"syscalls_output_{img}", f"syscalls_BIN_{img}", f"syscalls_unanalysed_{img}", "jna_ffi_analysis"):
        if (ws / d).is_dir():
            (v / "Binary_Analysis" / d).symlink_to(ws / d)
    for d in ("JARFILES", "LIBS", "BINARIES", "RUNTIME"):
        (v / "Dataset" / f"{d}_{img}").symlink_to(ws / f"{d}_{img}")
    # what this run does not produce (dynamic capture, run log, extra components) is the shipped one's
    for d in ("Dynamic_Analysis", "pipeline_run.log", "extra_components"):
        if (shipped / d).exists():
            (v / d).symlink_to(shipped / d)
    # the other images' columns come from the shipped results (only this column is read)
    for r in (table / sub).iterdir():
        if r.name != img and r.is_dir():
            (tv / r.name).symlink_to(r)
    # native-method mapping breakdown: the audit on this run's mapping
    swat = ["--swat-override", f"{img}={ART / 'swat4j' / 'outputs' / 'mapping' / img}"] if jdk8 else []
    run([sys.executable, str(ART / "analysis" / "native_mapping_audit" / "audit_native_mapping.py"),
         "--out", str(ws / "audit"), "--app", f"{img}={v}"] + swat, ws / "audit.log", echo=False)
    rows = list(csv.DictReader(open(table / "tables" / "mapping_audit_per_app.csv")))
    mine = next(csv.DictReader(open(ws / "audit" / "per_app_summary.csv")))
    with open(ws / "audit" / "table_audit.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        for r in rows:
            w.writerow({k: mine.get(k, r[k]) for k in r} if r["app"] == img else r)
    if jdk8:
        run([sys.executable, str(ART / "tools" / "make_tab_results_jdk8.py"), str(ws / "audit" / "table_audit.csv"),
             str(ws / "table")], ws / "table.log", check=False, echo=False, env={**os.environ, "RESULTS": str(tv)})
    else:
        run([sys.executable, str(ART / "tools" / "make_paper_table_latest.py"), str(tv), str(table / "manual_mapping"),
             str(ws / "audit" / "table_audit.csv"), str(ws / "table"), str(table / "runc.txt")],
            ws / "table.log", check=False, echo=False)
    lines = []
    for label, val in tex_column(ws / "table.tex", img):
        lines.append(f"      {label}" if val is None else f"      {label:40s}{val:>10s}")
    text = "\n".join(lines)
    (out / "table_column.txt").write_text(re.sub(r"(?m)^      ", "", text) + "\n")
    return text


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        sys.exit(__doc__)
    global QUIET
    QUIET = "-q" in sys.argv[1:]
    imgs = [a for a in sys.argv[1:] if a not in ("--no-run", "-q")]
    if imgs == ["all"]:
        imgs = sorted(p.parent.parent.name for t, s in TABLES for p in (t / s).glob("*/dataset/Dataset.tar.xz.part00"))
    for img in imgs:
        whitelist(img, run_container="--no-run" not in sys.argv[1:])


if __name__ == "__main__":
    main()
