#!/usr/bin/env python3
"""Recover syscall sites hidden behind glibc >= 2.41 cancellation wrappers.

Since glibc 2.41 a cancellable syscall wrapper such as fsync() no longer issues
`mov $NR,%eax; syscall` itself. It pushes the syscall number as the 7th
argument and calls __syscall_cancel (or __internal_syscall_cancel), which
reaches the `syscall` instruction in __syscall_cancel_arch with the number in a
register. SysPart's value-flow cannot resolve that number, so the site is
dropped and every syscall issued only this way (fsync, wait4, ...) is missing
from the results.

The number is a constant at each wrapper's call site (`push $0x4a; call
__syscall_cancel`). This script disassembles the libc that the call graph
loaded, finds those call sites, and prints one syscall-site line per wrapper in
SysPart's syscalls_with_callsites.txt format:

    <function> <addr> <module> <syscall-name> <number>

so getsyscalls attributes the syscall to the wrapper, exactly as SysPart does
for an inline syscall instruction. Prints nothing for an older glibc.

Usage: cancel_syscall_sites.py <analysed-binary> <callgraph.json>
"""

import json
import re
import subprocess
import sys
from pathlib import Path

CANCEL_FUNCS = ("__syscall_cancel", "__internal_syscall_cancel")
UNISTD = "/usr/include/x86_64-linux-gnu/asm/unistd_64.h"


def syscall_names() -> dict[int, str]:
    names = {}
    for line in Path(UNISTD).read_text().splitlines():
        m = re.match(r"#define __NR_(\w+)\s+(\d+)$", line)
        if m:
            names[int(m.group(2))] = m.group(1)
    return names


def candidate_libcs(app: Path) -> list[Path]:
    """libc.so.6 files the analysed binary could have loaded: under the dataset
    root (the directory above LIBS_*/BINARIES_*), else next to the binary."""
    real = app.resolve()
    roots = [p for p in (app.parent, *app.parents, real.parent, *real.parents)
             if p.name.startswith(("LIBS_", "BINARIES_"))]
    search = [r.parent for r in roots] or [app.parent]
    found = []
    for root in search:
        found += [p for p in root.rglob("libc.so.6") if p.is_file()]
    return list(dict.fromkeys(p.resolve() for p in found))


def cancel_sites(libc: Path) -> list[tuple[int, int]]:
    """(function start address, syscall number) for each wrapper that pushes a
    constant and calls a cancellation entry point."""
    starts = {}
    for line in subprocess.run(["nm", str(libc)], capture_output=True, text=True).stdout.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[1] in "tTwW":
            starts.setdefault(parts[2], int(parts[0], 16))
    if not any(f in starts for f in CANCEL_FUNCS):
        return []
    dis = subprocess.run(["objdump", "-d", "--no-show-raw-insn", str(libc)],
                         capture_output=True, text=True).stdout
    sites, func_addr, recent = [], None, []
    call_re = re.compile(r"call\s+[0-9a-f]+ <(%s)>" % "|".join(CANCEL_FUNCS))
    for line in dis.splitlines():
        m = re.match(r"^([0-9a-f]+) <(.+)>:$", line)
        if m:
            func_addr, recent = int(m.group(1), 16), []
            continue
        m = re.match(r"^\s*[0-9a-f]+:\s+(.*)$", line)
        if not m or func_addr is None:
            continue
        ins = m.group(1).strip()
        if call_re.search(ins):
            pushes = [p for p in recent if p.startswith("push")]
            imm = re.match(r"push\s+\$0x([0-9a-f]+)$", pushes[-1]) if pushes else None
            if imm:
                sites.append((func_addr, int(imm.group(1), 16)))
        recent = (recent + [ins])[-12:]
    return sites


def main(argv: list[str]) -> int:
    app, callgraph = Path(argv[0]), Path(argv[1])
    data = json.loads(callgraph.read_text())
    by_module = {}
    for f in data["functions"]:
        by_module.setdefault(f["module"], {})[int(f["addr"], 16)] = f["name"]
    libc_modules = [m for m in by_module if m.rsplit("/", 1)[-1].endswith("libc.so.6")]
    if not libc_modules:
        return 0
    names = syscall_names()
    for module in libc_modules:
        funcs = by_module[module]
        for libc in candidate_libcs(app):
            sites = cancel_sites(libc)
            if not sites:
                continue
            # The libc SysPart loaded must agree with this file on addresses.
            nm_out = subprocess.run(["nm", str(libc)], capture_output=True, text=True).stdout
            cancel_addr = {int(l.split()[0], 16) for l in nm_out.splitlines()
                           if l.split()[-1] in CANCEL_FUNCS and len(l.split()) == 3}
            if not cancel_addr & set(funcs):
                continue
            for addr, nr in sites:
                if addr in funcs and nr in names:
                    print(f"{funcs[addr]} {addr:x} {module} {names[nr]} {nr}")
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
