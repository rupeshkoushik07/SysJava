#!/usr/bin/env python3
"""
Tables for MAPPING_PER_LIBRARY.md from mechanism_ablation.py output.

  per_container.csv   one row per container: mapping coverage, entry points by
                      mechanism, libraries rooted, (library, syscall) pairs and
                      app-level unions for both arms, full and direct modes
  per_mechanism.csv   per (container set, mechanism): entry points, how many SWAT4J
                      also has, libraries rooted only by it, library-level
                      syscalls SWAT4J's mapping does not reach
  differing.csv       every (container, library) whose syscalls differ

Known SysJava false positives are kept out of the totals and listed separately
(EXCLUDE).
"""
import argparse
import csv
import os
from collections import Counter, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
# (container, library): reason. The detector read Groovy's VerifyClass Ant task as an
# FFM downcall into libverify; it is not a native binding.
EXCLUDE = {("groovy_4.0.0-jdk8-buster", "libverify.so"): "SysJava false positive (FFM detector)"}
JDK = {
    "zookeeper_3.4.14": "8", "tomcat_7.0": "8", "cassandra_3.0.29": "8", "orientdb_3.2.19": "8",
    "jruby_9.4.2.0": "8", "cassandra_5.0.6-bookworm": "17", "jetty_9.4.51-jdk8-buster": "8",
    "groovy_4.0.0-jdk8-buster": "8", "solr_8.7.0-jdk8-buster": "8",
    "tomcat_11.0.18": "25", "elasticsearch_7.1.0": "12", "jetty_latest": "25",
    "solr_slim": "25", "groovy_latest": "21", "zookeeper_latest": "17",
}
MECHS = ["JNI static", "RegisterNatives app", "RegisterNatives JVM", "JVM_ entry", "JNA",
         "JNR-FFI", "FFM", "manual bridge", "other"]


def read(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", nargs="+", required=True,
                    help="name=mechanism_ablation_out_dir (e.g. older=out_mech)")
    ap.add_argument("--audit", nargs="+", required=True, help="per_app_summary.csv files")
    ap.add_argument("--out", default=os.path.join(HERE, "out_mech_summary"))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    audit = {}
    for a in args.audit:
        for r in read(a):
            audit[r["app"]] = r

    cont_rows, mech_rows, diff_rows, excluded = [], [], [], []
    # An app present in several sets (Tomcat 11 is in both runs) is counted in the last one.
    owner = {}
    for spec in args.set:
        set_name, d = spec.split("=", 1)
        for r in read(os.path.join(d, "per_library.csv")):
            owner[r["app"]] = set_name
    for spec in args.set:
        set_name, d = spec.split("=", 1)
        libs = read(os.path.join(d, "per_library.csv"))
        mechs = read(os.path.join(d, "mechanisms.csv"))
        apps = [a for a in OrderedDict.fromkeys(r["app"] for r in libs) if owner[a] == set_name]
        mech_tot = OrderedDict((m, Counter()) for m in MECHS)
        for app in apps:
            a = audit.get(app, {})
            row = OrderedDict(set=set_name, app=app, jdk=JDK.get(app, ""),
                              native_methods=a.get("denominator", ""),
                              sysjava_mapped=a.get("et_mapped", ""), swat4j_mapped=a.get("sw_mapped", ""))
            ep = Counter()
            for mode in ("full", "direct"):
                rows = [r for r in libs if r["app"] == app and r["mode"] == mode]
                kept = []
                for r in rows:
                    if (app, r["lib"]) in EXCLUDE:
                        if mode == "full":
                            excluded.append(dict(app=app, lib=r["lib"], reason=EXCLUDE[(app, r["lib"])],
                                                 sysjava_syscalls=r["sysjava_syscalls"]))
                        continue
                    kept.append(r)
                sj_u, sw_u, sj_pairs, sw_pairs = set(), set(), 0, 0
                for r in kept:
                    sj, sw = set(r["sysjava_set"].split()), set(r["swat4j_set"].split())
                    sj_u |= sj
                    sw_u |= sw
                    sj_pairs += len(sj)
                    sw_pairs += len(sw)
                    if mode == "full":
                        for kv in r["sysjava_mechanisms"].split():
                            k, v = kv.rsplit(":", 1)
                            ep[k.replace("_", " ").replace("JVM  entry", "JVM_ entry")] += int(v)
                    if sj != sw:
                        diff_rows.append(dict(set=set_name, app=app, lib=r["lib"], mode=mode,
                                              sysjava_mechanisms=r["sysjava_mechanisms"],
                                              swat4j_starts=r["swat4j_starts"],
                                              sysjava_syscalls=len(sj), swat4j_syscalls=len(sw),
                                              missed=" ".join(sorted(sj - sw)),
                                              swat4j_only=" ".join(sorted(sw - sj))))
                if mode == "full":
                    row["libs_analysed"] = len(kept)
                    row["libs_rooted_sysjava"] = sum(int(r["sysjava_starts"]) > 0 for r in kept)
                    row["libs_rooted_swat4j"] = sum(int(r["swat4j_starts"]) > 0 for r in kept)
                    row["libs_unrooted_by_swat4j"] = " ".join(
                        r["lib"] for r in kept if int(r["sysjava_starts"]) > 0 and int(r["swat4j_starts"]) == 0)
                    row["entry_points_sysjava"] = sum(int(r["sysjava_starts"]) for r in kept)
                    row["entry_points_swat4j"] = sum(int(r["swat4j_starts"]) for r in kept)
                row["%s_lib_syscall_pairs_sysjava" % mode] = sj_pairs
                row["%s_lib_syscall_pairs_swat4j" % mode] = sw_pairs
                row["%s_union_sysjava" % mode] = len(sj_u)
                row["%s_union_swat4j" % mode] = len(sw_u)
                row["%s_union_missed" % mode] = " ".join(sorted(sj_u - sw_u))
            row["entry_points_by_mechanism"] = " ".join("%s=%d" % (k, v) for k, v in ep.items())
            cont_rows.append(row)
            for r in mechs:
                if r["app"] != app or (app, r["lib"]) in EXCLUDE:
                    continue
                t = mech_tot[r["mechanism"]]
                if r["mode"] == "full":
                    t["entry_points"] += int(r["starts"])
                    t["also_in_swat4j"] += int(r["starts_also_in_swat4j"])
                    t["containers"] += 0
                    t["libraries"] += 1
                t["%s_lib_syscalls_not_reached_by_swat4j" % r["mode"]] += int(r["not_reached_by_swat4j"])
            mech_apps = {(r["app"], r["mechanism"]) for r in mechs
                         if r["app"] == app and r["mode"] == "full" and (app, r["lib"]) not in EXCLUDE}
            for _, m in mech_apps:
                mech_tot[m]["containers"] += 1
        for m, t in mech_tot.items():
            if t["libraries"]:
                mech_rows.append(dict(set=set_name, mechanism=m, containers=t["containers"],
                                      libraries=t["libraries"], entry_points=t["entry_points"],
                                      also_in_swat4j=t["also_in_swat4j"],
                                      full_lib_syscalls_not_reached_by_swat4j=t["full_lib_syscalls_not_reached_by_swat4j"],
                                      direct_lib_syscalls_not_reached_by_swat4j=t["direct_lib_syscalls_not_reached_by_swat4j"]))

    def write(name, rows):
        if rows:
            with open(os.path.join(args.out, name), "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)

    write("per_container.csv", cont_rows)
    write("per_mechanism.csv", mech_rows)
    write("differing.csv", diff_rows)
    write("excluded.csv", excluded)


if __name__ == "__main__":
    main()
