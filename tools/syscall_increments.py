#!/usr/bin/env python3
"""Per-component syscall increments of the paper's allowlist tables (Table III, Table V).

Input: one <image>.json per image with the syscall sets the table generator uses
(tools/make_tab_results_jdk8.py, tools/make_paper_table_latest.py):
  java      Java-library syscalls (bindings, JNA/FFI, libjvm imports, manual mappings)
  binary    syscalls of the executables observed at run time
  unan_raw  syscalls of the libraries loaded without a recovered binding
  runc_raw  container-runtime allowlist (runc.txt)

Rows, each counting only syscalls not in the rows above:
  Java (base), Observed-binaries (+Delta), Docker runtime (Delta), Fallback libraries (Delta), Total.

Usage:
  tools/syscall_increments.py 2_swat4j_vs_sysjava/tables/increments   # Table V
  tools/syscall_increments.py 1_latest_containers/tables/increments   # Table III
"""
import glob
import json
import os
import sys


def main(folder):
    print(f"{'image':34} {'Java':>5} {'+Bin':>5} {'+runc':>6} {'+Fallback':>9} {'Total':>6}")
    for p in sorted(glob.glob(os.path.join(folder, "*.json"))):
        s = {k: set(v) for k, v in json.load(open(p)).items()}
        java = s["java"]
        binary = s["binary"] - java
        runc = s["runc_raw"] - java - binary
        fallback = s["unan_raw"] - java - binary - runc
        total = java | binary | runc | fallback
        print(f"{os.path.basename(p)[:-5]:34} {len(java):>5} {len(binary):>5} {len(runc):>6} {len(fallback):>9} {len(total):>6}")


if __name__ == "__main__":
    main(sys.argv[1])
