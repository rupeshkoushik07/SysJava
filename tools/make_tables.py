#!/usr/bin/env python3
"""Rebuild the per-container rows of the paper tables from pipeline results.

    make_tables.py <set> <results_dir> --runtime runc.txt [more.txt] --out <dir> [--audit per_app_summary.csv]

<set> is "latest" (Table tab:latest) or "jdk8" (Table tab:results). Each
subfolder <results_dir>/<target>/ is one pipeline result (layout written by
pipelines/*/scripts/organize_results.sh). Writes <out>/table.csv, table.md and
table_rows.tex (rows in the paper's column order; '-' where a result is missing).

Syscall-allowlist rows (all sets are syscall names, one per line):
  Java Lib Syscalls         = Binary_Analysis/syscalls_output_<t>/library_syscalls.txt
                              U Binary_Analysis/jna_ffi_analysis/union_syscalls.txt
  Container Binary Syscalls = Binary_Analysis/syscalls_BIN_<t>/binary_syscalls.txt
  Runtime Set, Additional   = runtime set (<t>/runtime_set.txt if present, else
                              --runtime) minus (Java lib U binary)
  Library Fallback (delta)  = Binary_Analysis/syscalls_unanalysed_<t>/unanalysed_syscalls.txt
                              minus everything above
  Total Syscalls            = syscalls in the seccomp profile <t>.json
The script checks that Total equals the union of the four sets.

Artefact rows come from Dynamic_Analysis/sysdig_outputs_<t>/ (observed) and the
SysPart output folders (analysed). Bytecode rows count the detector outputs in
Bytecode_Analysis/outputs_<t>/. Native-declaration coverage rows (accounted,
JNI static/partial/dynamic, not found) come from the mapping audit
(analysis/native_mapping_audit, column names of its per_app_summary.csv) when
--audit is given.
"""
import argparse
import csv
import json
import os
import sys

COLUMNS = {
    "latest": [
        ("cassandra_5.0.8", "Cassandra 5.0.8"), ("zookeeper_3.9.5", "Zookeeper 3.9.5"),
        ("tomcat_11.0.22", "Tomcat 11.0.22"), ("solr_10.0.0", "Solr 10.0.0"),
        ("groovy_5.0.6", "Groovy 5.0.6"), ("orientdb_3.2.53", "OrientDB 3.2.53"),
        ("jetty_12.1.10", "Jetty 12.1.10"), ("elasticsearch_7.1.0", "Elasticsearch 7.1.0"),
        ("storm_2.8.8", "Storm 2.8.8"), ("jruby_10.1.0.0", "JRuby 10.1.0.0"),
    ],
    "jdk8": [
        ("jetty_9.4.51-jdk8-buster", "Jetty 9.4.51"), ("storm_2.4.0-jdk8-buster", "Storm 2.4.0"),
        ("elasticsearch_7.5.2-jdk8-buster", "Elasticsearch 7.5.2"),
        ("solr_8.7.0-jdk8-buster", "Solr 8.7.0"), ("groovy_4.0.0-jdk8-buster", "Groovy 4.0.0"),
        ("zookeeper_3.4.14", "Zookeeper 3.4.14"), ("tomcat_7.0", "Tomcat 7.0"),
        ("cassandra_3.0.29", "Cassandra 3.0.29"), ("orientdb_3.2.19", "OrientDB 3.2.19"),
        ("jruby_9.4.2.0", "JRuby 9.4.2.0"),
    ],
}

AUDIT_ROWS = [  # (row label, per_app_summary.csv column)
    ("Native Declarations", "denominator"),
    ("SysJava Accounted For", "et_accounted"),
    ("  JNI Static (Java_*)", "et_jni_static"),
    ("  Partial (_1/$/__)", "et_jni_partial"),
    ("  JNI Dynamic: JVM (RegisterNatives)", "et_registered"),
    ("  Platform / Intrinsic", "et_platform"),
    ("  Not Found", "et_not_found"),
    ("SWAT4J Resolved", "sw_accounted"),
    ("  SWAT4J Not Found", "sw_not_found"),
]


def read_set(path):
    if not os.path.isfile(path):
        return None
    with open(path, errors="replace") as f:
        return {l.strip().strip('"') for l in f if l.strip() and not l.startswith("#")}


def count_lines(path, skip_comments=True):
    if not os.path.isfile(path):
        return None
    with open(path, errors="replace") as f:
        return sum(1 for l in f if l.strip() and not (skip_comments and l.startswith("#")))


def profile_syscalls(path):
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        prof = json.load(f)
    names = set()
    for rule in prof.get("syscalls", []):
        names.update(rule.get("names", []))
    return names


def subdirs(path):
    if not os.path.isdir(path):
        return None
    return sorted(d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d)))


def target_row(root, t, runtime):
    d = os.path.join(root, t)
    ba = os.path.join(d, "Binary_Analysis")
    out = os.path.join(d, "Bytecode_Analysis", f"outputs_{t}")
    dyn = os.path.join(d, "Dynamic_Analysis", f"sysdig_outputs_{t}")
    row = {"target": t, "present": os.path.isdir(d) and not os.path.isfile(os.path.join(d, "PENDING.md"))}
    if not row["present"]:
        return row
    # A result produced with a different runtime set carries it with it.
    own = read_set(os.path.join(d, "runtime_set.txt"))
    if own is not None:
        runtime = own

    lib = read_set(os.path.join(ba, f"syscalls_output_{t}", "library_syscalls.txt"))
    jna = read_set(os.path.join(ba, "jna_ffi_analysis", "union_syscalls.txt")) or set()
    binr = read_set(os.path.join(ba, f"syscalls_BIN_{t}", "binary_syscalls.txt"))
    unan = read_set(os.path.join(ba, f"syscalls_unanalysed_{t}", "unanalysed_syscalls.txt")) or set()
    total = profile_syscalls(os.path.join(ba, f"syscalls_output_{t}", f"{t}.json"))

    if lib is not None:
        row["  of which JNA/FFI only"] = len(jna - lib)
        lib = lib | jna
        row["Java Lib Syscalls"] = len(lib)
    if binr is not None:
        row["Container Binary Syscalls"] = len(binr)
    if lib is not None and binr is not None:
        row["Runtime Set, Additional"] = len(runtime - lib - binr)
        row["Library Fallback (delta)"] = len(unan - lib - binr - runtime)
        union = lib | binr | runtime | unan
        if total is not None:
            row["Total Syscalls"] = len(total)
            row["check: total == union"] = "ok" if total == union else \
                f"DIFF profile-only={sorted(total - union)} union-only={sorted(union - total)}"
    elif total is not None:
        row["Total Syscalls"] = len(total)

    # Detector outputs
    row["Native methods (detector)"] = count_lines(os.path.join(out, "native_methods.txt"))
    row["JVM RegisterNatives bindings"] = count_lines(os.path.join(out, "jvm_dynamic_mapping.txt"))
    row["App RegisterNatives bindings"] = count_lines(os.path.join(out, "jni_dynamic_bindings.txt"))
    row["JNA hits"] = count_lines(os.path.join(out, "jna_hits.txt"))
    row["FFI/FFM hits"] = count_lines(os.path.join(out, "ffi_hits.txt"))
    row["JNR-FFI hits"] = count_lines(os.path.join(out, "jnr_ffi_hits.txt"))

    # Artefacts
    row["Libraries Observed"] = count_lines(os.path.join(dyn, "libs_loaded_raw.txt"))
    row["Executables Observed"] = count_lines(os.path.join(dyn, f"binaries_unique_{t}.txt"))
    row["JARs Observed"] = count_lines(os.path.join(dyn, f"jars_unique_{t}.txt"))
    libs = subdirs(os.path.join(ba, f"syscalls_output_{t}"))
    row["Libraries Analysed"] = len(libs) if libs is not None else None
    bins = subdirs(os.path.join(ba, f"syscalls_BIN_{t}"))
    row["Executables Analysed"] = len(bins) if bins is not None else None

    # Runtime check under the generated profile
    for cand in (os.path.join(d, "seccomp_runtime_test.log"),
                 os.path.join(ba, f"syscalls_output_{t}", "seccomp_runtime_test.log")):
        if os.path.isfile(cand):
            res = [l.strip() for l in open(cand, errors="replace") if "RESULT=" in l]
            row["Runs under profile"] = res[-1].split("RESULT=", 1)[1] if res else "?"
            break
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("set", choices=sorted(COLUMNS))
    ap.add_argument("results_dir")
    ap.add_argument("--runtime", required=True, nargs="+", help="runtime syscall set file(s): runc.txt [+ additions]")
    ap.add_argument("--audit", help="per_app_summary.csv from the native-mapping audit")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    runtime = set().union(*[(read_set(p) or set()) for p in a.runtime])
    cols = COLUMNS[a.set]
    rows = {t: target_row(a.results_dir, t, runtime) for t, _ in cols}

    if a.audit and os.path.isfile(a.audit):
        with open(a.audit) as f:
            audit = {r["app"]: r for r in csv.DictReader(f)}
        for t, _ in cols:
            r = audit.get(t)
            if r:
                for label, col in AUDIT_ROWS:
                    rows[t][label] = r.get(col)

    labels = []
    for label, _ in AUDIT_ROWS:
        if any(label in r for r in rows.values()):
            labels.append(label)
    for r in rows.values():
        for k in r:
            if k not in ("target", "present") and k not in labels:
                labels.append(k)

    os.makedirs(a.out, exist_ok=True)
    fmt = lambda v: "-" if v is None else str(v)
    with open(os.path.join(a.out, "table.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["row"] + [t for t, _ in cols])
        for lab in labels:
            w.writerow([lab.strip()] + [fmt(rows[t].get(lab)) for t, _ in cols])
    with open(os.path.join(a.out, "table.md"), "w") as f:
        f.write("| | " + " | ".join(n for _, n in cols) + " |\n")
        f.write("|---|" + "---|" * len(cols) + "\n")
        for lab in labels:
            f.write(f"| {lab.strip()} | " + " | ".join(fmt(rows[t].get(lab)) for t, _ in cols) + " |\n")
        missing = [t for t, _ in cols if not rows[t]["present"]]
        if missing:
            f.write(f"\nNo results yet for: {', '.join(missing)}\n")
    with open(os.path.join(a.out, "table_rows.tex"), "w") as f:
        f.write("% generated by tools/make_tables.py -- paste rows into the paper table\n")
        for lab in labels:
            if lab.startswith("check") or lab == "Runs under profile":
                continue
            f.write(lab.strip().replace("_", r"\_").replace("$", r"\$") + " & "
                    + " & ".join(fmt(rows[t].get(lab)) for t, _ in cols) + r" \\" + "\n")
    print(open(os.path.join(a.out, "table.md")).read())
    bad = [t for t, _ in cols if str(rows[t].get("check: total == union", "ok")) != "ok"]
    if bad:
        print("WARNING: profile != union of sets for " + ", ".join(bad), file=sys.stderr)


if __name__ == "__main__":
    main()
