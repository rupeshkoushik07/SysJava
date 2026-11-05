#!/usr/bin/env python3
"""Check that every overload of an overloaded JNI native method is mapped.

An overloaded Java native method has one exported symbol per signature,
Java_<cls>_<name>__<mangled-args> (JNI spec, "long name"). Before commit
642a71c the mapper kept only the first target per Java method, so the other
overloads never reached SysPart as start functions.

For each library under LIBS_DIR this finds exported Java_* symbols that share a
short name with another export (an overload group), keeps the groups whose
Java method was detected by the bytecode stage (native_methods.txt), and checks
that every symbol of the group appears in mapped_method_syscalls.txt and in the
library's start-function file under OUTPUTS_DIR.

Usage: check_jni_overloads.py <LIBS_DIR> <OUTPUTS_DIR> [report.tsv]
Exit status 1 when a detected overload is missing from the mapping.
"""

import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


def exported_jni(lib: Path) -> list[str]:
    out = subprocess.run(["nm", "-D", "--defined-only", str(lib)], text=True,
                         capture_output=True).stdout
    # Strip symbol versions (Java_...@@SUNWprivate_1.1); the mapper records bare names.
    return [line.split()[-1].split("@", 1)[0] for line in out.splitlines()
            if line.split() and line.split()[-1].startswith("Java_")]


def java_name(symbol: str) -> str:
    """Java_java_io_FileInputStream_open0__Ljava... -> java.io.FileInputStream.open0
    (JNI escapes: _1 = '_', _0xxxx = unicode; overload suffix after '__')."""
    short = symbol[len("Java_"):].split("__", 1)[0]
    parts = re.split(r"_(?![0-9])", short)
    return ".".join(p.replace("_1", "_") for p in parts)


def main(argv: list[str]) -> int:
    libs, outputs = Path(argv[0]), Path(argv[1])
    report = Path(argv[2]) if len(argv) > 2 else outputs / "jni_overload_check.tsv"

    detected = set()
    for line in (outputs / "native_methods.txt").read_text(errors="replace").splitlines():
        token = line.strip().split()[0] if line.strip() else ""
        token = token.split("(", 1)[0]
        if token:
            detected.add(token)

    mapped_symbols = set()
    mapped = outputs / "mapped_method_syscalls.txt"
    if mapped.is_file():
        for line in mapped.read_text(errors="replace").splitlines():
            if " -> " in line:
                mapped_symbols.add(line.split(" -> ", 1)[1].split()[0])

    rows, missing = [], 0
    for lib in sorted(p for p in libs.rglob("*.so*") if p.is_file() and not p.is_symlink()):
        groups = defaultdict(list)
        for sym in exported_jni(lib):
            groups[sym.split("__", 1)[0]].append(sym)
        start_files = list(outputs.rglob(f"{lib.name}.txt"))
        starts = set()
        for sf in start_files:
            starts.update(l.strip() for l in sf.read_text(errors="replace").splitlines() if l.strip())
        for short, syms in sorted(groups.items()):
            if len(syms) < 2:
                continue
            method = java_name(short)
            if method not in detected:
                continue
            for sym in sorted(syms):
                in_map, in_start = sym in mapped_symbols, sym in starts
                missing += not in_map
                rows.append((lib.name, method, sym, "yes" if in_map else "NO",
                             "yes" if in_start else ("NO" if start_files else "no-start-file")))

    with report.open("w") as handle:
        handle.write("library\tjava_method\tjni_symbol\tin_mapping\tin_start_file\n")
        for row in rows:
            handle.write("\t".join(row) + "\n")
    groups_n = len({(r[0], r[1]) for r in rows})
    print(f"overloaded JNI methods detected: {groups_n} ({len(rows)} symbols); "
          f"missing from mapping: {missing}; report: {report}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
