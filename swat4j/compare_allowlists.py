#!/usr/bin/env python3
"""Compare EchoTrace seccomp allowlists against SWAT4J allowlists.

Usage: compare_allowlists.py <echotrace_results_dir> <swat4j_result_dir> <out_dir> [rerun_dir [dynamic_dir]]

  echotrace_results_dir  e.g. EchoTrace/Final_results_echotrace
  swat4j_result_dir      SWAT4J repo's result/ (published lists)
  rerun_dir              optional dir with <app>_syscalls.txt from a fresh SWAT4J static run
  dynamic_dir            optional dir with <app>_result.txt from dynamic_swat4j.sh

SWAT4J names syscalls via `ausyscall`, which calls #17/#18 "pread"/"pwrite"; Docker
profiles and strace call them "pread64"/"pwrite64". Those two are aliased before comparing.
"""
import csv
import json
import os
import sys

# SWAT4J app name -> EchoTrace results folder
APPS = {
    "tomcat": "tomcat_7.0",
    "jetty": "jetty_9.4.51",
    "orientdb": "orientdb_3.2.19",
    "cassandra": "cassandra_3.0.29",
    "elasticsearch": "elasticsearch_7.5.2",
    "solr": "solr_8.7.0",
    "zookeeper": "zookeeper_3.4.14",
    "storm": "storm_2.4.0",
    "groovy": "groovy_4.0.0",
    "jruby": "jruby_9.4.2.0",
}


# ausyscall name -> Docker/libseccomp name for the same syscall number
ALIASES = {"pread": "pread64", "pwrite": "pwrite64"}


def read_list(path):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        names = {l.strip().strip('"') for l in f if l.strip() and not l.startswith("#")}
    return {ALIASES.get(n, n) for n in names}


def union(*loads):
    def load(app):
        sets = [l(app) for l in loads]
        return None if any(s is None for s in sets) else set().union(*sets)
    return load


def read_echotrace(et_dir, folder):
    path = os.path.join(et_dir, folder, "Binary_Analysis", f"syscalls_output_{folder}", f"{folder}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        profile = json.load(f)
    names = set()
    for rule in profile.get("syscalls", []):
        if rule.get("action") == "SCMP_ACT_ALLOW":
            names.update(rule.get("names", []))
    return names


def compare(a, b):
    return {
        "both": len(a & b),
        "only_et": len(a - b),
        "only_swat": len(b - a),
        "jaccard": round(len(a & b) / len(a | b), 3) if a | b else 1.0,
    }


def main():
    et_dir, swat_dir, out_dir = sys.argv[1:4]
    rerun_dir = sys.argv[4] if len(sys.argv) > 4 else None
    dynamic_dir = sys.argv[5] if len(sys.argv) > 5 else None
    os.makedirs(out_dir, exist_ok=True)

    baselines = {
        "swat_static": lambda app: read_list(os.path.join(swat_dir, "static", "result_final", f"{app}_444.txt")),
        "swat_combined": lambda app: read_list(os.path.join(swat_dir, "combine", f"{app}.txt")),
        "swat_dynamic": lambda app: read_list(os.path.join(swat_dir, "dynamic", f"{app}_result.txt")),
    }
    if rerun_dir:
        baselines["swat_rerun"] = lambda app: read_list(os.path.join(rerun_dir, f"{app}_syscalls.txt"))
    if dynamic_dir:
        baselines["swat_redyn"] = lambda app: read_list(os.path.join(dynamic_dir, f"{app}_result.txt"))
        baselines["swat_refull"] = union(baselines["swat_rerun"], baselines["swat_redyn"])

    rows = []
    details = []
    for app, folder in APPS.items():
        et = read_echotrace(et_dir, folder)
        if et is None:
            print(f"[!] no EchoTrace profile for {folder}")
            continue
        row = {"app": folder, "echotrace": len(et)}
        details.append(f"## {folder}\n\nEchoTrace: {len(et)} syscalls\n")
        for name, load in baselines.items():
            other = load(app)
            if other is None:
                row[name] = ""
                continue
            c = compare(et, other)
            row[name] = len(other)
            row[f"{name}_both"] = c["both"]
            row[f"{name}_only_et"] = c["only_et"]
            row[f"{name}_only_swat"] = c["only_swat"]
            row[f"{name}_jaccard"] = c["jaccard"]
            details.append(f"### vs {name} ({len(other)} syscalls, jaccard {c['jaccard']})\n")
            details.append(f"- only EchoTrace ({c['only_et']}): {' '.join(sorted(et - other))}")
            details.append(f"- only SWAT4J ({c['only_swat']}): {' '.join(sorted(other - et))}\n")
        rows.append(row)

    fields = ["app", "echotrace"]
    for name in baselines:
        fields += [name, f"{name}_both", f"{name}_only_et", f"{name}_only_swat", f"{name}_jaccard"]
    with open(os.path.join(out_dir, "summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(out_dir, "details.md"), "w") as f:
        f.write("\n".join(details) + "\n")

    hdr = f"{'app':<20}{'ET':>5}"
    for name in baselines:
        hdr += f" | {name:>13} both onlyET onlySW  jacc"
    print(hdr)
    for r in rows:
        line = f"{r['app']:<20}{r['echotrace']:>5}"
        for name in baselines:
            if r.get(name) == "":
                line += f" | {'-':>13}" + " " * 28
            else:
                line += (f" | {r[name]:>13} {r[name + '_both']:>4} {r[name + '_only_et']:>6}"
                         f" {r[name + '_only_swat']:>6} {r[name + '_jaccard']:>5}")
        print(line)


if __name__ == "__main__":
    main()
