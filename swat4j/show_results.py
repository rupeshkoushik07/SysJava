#!/usr/bin/env python3
"""Print the SysJava vs SWAT4J table (JDK 8, Debian 10 images) from a packaged outputs
folder (package_outputs_jdk8deb.sh). Needs only Python 3; nothing is rerun.

  python3 show_results.py [outputs_dir] [--sets]  (default: outputs_jdk8_debian10 next to this file;
                                                  --sets also lists the syscalls only in A / only in B)

Rules (same as the paper's table):
  SWAT4J total B = static allowlist  U  dynamic allowlist
  SysJava A      = SCMP_ACT_ALLOW names of SysJava's seccomp profile
  ausyscall's "pread"/"pwrite" = "pread64"/"pwrite64" (same syscall numbers); no other filtering
  A dynamic trace counts only if no other container started during it (dynamic_runs.tsv)
"""
import csv
import os
import sys

APPS = [("zookeeper", "Zookeeper", "3.4.14"), ("tomcat", "Tomcat", "7.0"),
        ("cassandra", "Cassandra", "3.0.29"), ("jetty", "Jetty", "9.4.51"),
        ("storm", "Storm", "2.4.0"), ("orientdb", "OrientDB", "3.2.19"),
        ("elasticsearch", "Elasticsearch", "7.5.2"), ("solr", "Solr", "8.7.0"),
        ("groovy", "Groovy", "4.0.0"), ("jruby", "JRuby", "9.4.2.0")]
ALIASES = {"pread": "pread64", "pwrite": "pwrite64"}
NOTES = {"storm": "sync is left out of SysJava's profile: it comes only from FFM calls inferred from Clojure class "
                  "names (JDK 8 has no FFM API); Storm runs under the 172-syscall profile.",
         "elasticsearch": "SysPart could not analyse the ML `controller` binary; its syscalls come "
                          "from the functions it imports (sysjava/elasticsearch_ml_component_imports.md)."}


def read_list(path):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return {ALIASES.get(l.strip(), l.strip()) for l in f if l.strip()}


def read_tsv(path, delimiter="\t"):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return list(csv.DictReader(f, delimiter=delimiter))


def mapping_counts(path):
    """Strategy counts from mapping/<app>.tsv (one row per native method SWAT4J's JTracer found)."""
    if not os.path.exists(path):
        return {}
    rows = read_tsv(path)
    out = {s: sum(r["strategy"] == s for r in rows) for s in ("Java_XXX", "JVM_XXX", "NETTY_HEURISTIC", "UNMAPPED")}
    out["MAPPED"] = len(rows) - out["UNMAPPED"]
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    d = args[0] if args else os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                            "outputs_jdk8_debian10")
    clean = {}
    for r in read_tsv(os.path.join(d, "dynamic", "dynamic_runs.tsv")):
        clean[r["app"]] = r["other_container_starts"].strip() == "none"  # last try wins
    seconds = {r["app"]: r["seconds"] for r in read_tsv(os.path.join(d, "dynamic", "timing.csv"), ",")}
    source = {r["app"]: r for r in read_tsv(os.path.join(d, "sysjava", "SOURCE.tsv"))}

    cols = []
    for app, label, ver in APPS:
        sj = read_list(os.path.join(d, "sysjava", f"{app}.txt"))
        st = read_list(os.path.join(d, "static", "syscalls", f"{app}.txt"))
        dy = read_list(os.path.join(d, "dynamic", f"{app}_result.txt")) if clean.get(app) else None
        nat = read_list(os.path.join(d, "static", "native_methods", f"{app}.txt"))
        mp = mapping_counts(os.path.join(d, "mapping", f"{app}.tsv"))
        full = st | dy if st is not None and dy is not None else None
        c = dict(A=sj, B=full, static=st, dynamic=dy, natives=nat,
                 runtime=source.get(app, {}).get("result"), startup=seconds.get(app) if dy is not None else None,
                 mapped=mp.get("MAPPED"), jni=mp.get("Java_XXX"), jvm=mp.get("JVM_XXX"),
                 heur=mp.get("NETTY_HEURISTIC"), unmapped=mp.get("UNMAPPED"))
        if sj is not None and full is not None:
            c.update(both=sj & full, only_a=sj - full, only_b=full - sj)
        cols.append(c)

    def v(c, k):
        x = c.get(k)
        if x is None:
            return "pending"
        return str(len(x)) if isinstance(x, set) else str(x)

    rows = [("SysJava total (A)", "A"), ("SWAT4J static + dynamic (B)", "B"),
            ("  SWAT4J static (JTracer + binary_analyser)", "static"),
            ("  SWAT4J dynamic (containerd startup trace)", "dynamic"),
            ("A and B", "both"), ("only A", "only_a"), ("only B", "only_b"),
            ("SysJava runtime check", "runtime"), ("Startup traced (s)", "startup"),
            ("Native methods SWAT4J finds (JTracer)", "natives"), ("  mapped by SWAT4J", "mapped"),
            ("    Java_* symbol name", "jni"), ("    JVM_* table", "jvm"),
            ("    Netty name rule", "heur"), ("  not mapped", "unmapped")]
    md = ["| | " + " | ".join(f"{l} {ver}" for _, l, ver in APPS) + " |", "|---" * (len(APPS) + 1) + "|"]
    for name, k in rows:
        vals = [v(c, k) + (f"<sup>{chr(97 + list(NOTES).index(app))}</sup>" if k == "A" and app in NOTES else "")
                for c, (app, _, _) in zip(cols, APPS)]
        md.append(f"| {name} | " + " | ".join(vals) + " |")
    print("\n".join(md))
    for i, (app, note) in enumerate(NOTES.items()):
        print(f"\n<sup>{chr(97 + i)}</sup> {app}: {note}")
    if "--sets" in sys.argv:
        for c, (app, _, _) in zip(cols, APPS):
            if "both" in c:
                print(f"\n{app}\n  only A: {' '.join(sorted(c['only_a']))}\n  only B: {' '.join(sorted(c['only_b']))}")


if __name__ == "__main__":
    main()
