#!/usr/bin/env python3
"""SysJava vs SWAT4J table (Table tab:results) from a SysJava results folder.

Runs swat4j/make_paper_table.py with two adaptations for the artifact layout:
  * the five rebuilt images are in <name>-jdk8-buster folders (e.g.
    jetty_9.4.51-jdk8-buster); make_paper_table.py looks for jetty_9.4.51;
  * images without a SysJava profile yet are left out of the table and listed,
    instead of stopping the script.

Usage: swat4j_table.py <sysjava results dir> <swat4j static dir> <swat4j dynamic dir> <out prefix>
Writes <out prefix>.md and <out prefix>.tex
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "swat4j"))
import make_paper_table as m  # noqa: E402


def profile(et_dir, folder):
    for name in (folder, folder + "-jdk8-buster"):
        path = os.path.join(et_dir, name, "Binary_Analysis", f"syscalls_output_{name}", f"{name}.json")
        if os.path.isfile(path):
            return path
    return None


def read_sysjava(et_dir, folder):
    with open(profile(et_dir, folder)) as f:
        rules = json.load(f)["syscalls"]
    return set().union(*[set(r["names"]) for r in rules if r.get("action") == "SCMP_ACT_ALLOW"])


def main():
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    et_dir = sys.argv[1]
    missing = [a[1] for a in m.APPS if profile(et_dir, a[1]) is None]
    m.APPS = [a for a in m.APPS if a[1] not in missing]
    m.read_sysjava = read_sysjava
    if missing:
        print("No SysJava profile yet, left out of the table: " + ", ".join(missing), file=sys.stderr)
    if not m.APPS:
        sys.exit("no SysJava profiles found in " + et_dir)
    m.main()


if __name__ == "__main__":
    main()
