#!/usr/bin/env python3
"""Second pass for ELFs that symbolize_dataset.py left without symbols.

Reads <results-root>/<target>/Dataset_symbolized/symbols.tsv, and for every row
still NOT_FOUND looks the file's owning package up again in the running
et_<target> container and tries every package source symbolize_dataset.py
knows (now including Debian's own debug pools). Only debug files whose GNU
Build ID matches are pooled.

Without --apply it only downloads and reports. With --apply each newly found
debug file is merged into the Dataset_symbolized copy (eu-unstrip + strip
--strip-debug, swapped in with an atomic rename) and its symbols.tsv row
becomes SYMBOLIZED. Analyses that already used the stripped copy must be rerun
afterwards; the list of changed files is printed.

Usage:
  RESULTS_ROOT=Final_results_JDK8 python3 scripts/fetch_missing_symbols.py [--apply] [target ...]
"""

from __future__ import annotations

import csv
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import symbolize_dataset as sd  # noqa: E402


def main(argv: list[str]) -> int:
    apply = "--apply" in argv
    targets = [a for a in argv if not a.startswith("--")] or sorted(
        p.name for p in sd.RESULTS_ROOT.iterdir() if (p / "Dataset_symbolized" / "symbols.tsv").is_file())
    (sd.POOL / "build-id").mkdir(parents=True, exist_ok=True)
    changed: list[str] = []
    for target in targets:
        tsv = sd.RESULTS_ROOT / target / "Dataset_symbolized" / "symbols.tsv"
        with tsv.open() as handle:
            rows = list(csv.reader(handle, delimiter="\t"))
        header, body = rows[0], rows[1:]
        missing = {r[1]: r for r in body if len(r) > 2 and r[2] == "NOT_FOUND" and r[1]}
        if not missing:
            print(f"[{target}] nothing missing")
            continue
        names = {Path(r[0]).name for r in missing.values()}
        urls: set[str] = set()
        for container in sd.sibling_containers(target):
            try:
                # Dependencies are copied under their soname, which inside the
                # container is a symlink (libseccomp.so.2 -> libseccomp.so.2.3.3);
                # container_paths() lists regular files only, so match links too.
                expr = " -o ".join(f"-name '{n}'" for n in sorted(names))
                listed = subprocess.run(
                    ["docker", "exec", container, "sh", "-c", f"find / -xdev \\( {expr} \\) 2>/dev/null"],
                    text=True, capture_output=True, timeout=600).stdout.split()
                owners = sd.package_owners(container, sorted({p for p in listed if p.startswith("/")}))
            except (subprocess.SubprocessError, OSError) as exc:
                print(f"[{container}] lookup failed: {exc}")
                continue
            for owner in owners:
                urls.update(sd.package_urls(*owner))
        wanted = {bid for bid in missing if not (sd.POOL / "build-id" / f"{bid}.debug").is_file()}
        for url in sorted(urls):
            if not wanted:
                break
            wanted -= sd.harvest_package(url, wanted, sd.POOL)
        found = [bid for bid in missing if (sd.POOL / "build-id" / f"{bid}.debug").is_file()]
        print(f"[{target}] {len(found)}/{len(missing)} previously missing Build IDs now have a verified .debug")
        for bid in found:
            print(f"    {missing[bid][0]}")
        if not apply:
            continue
        out_root = tsv.parent
        for row in body:
            if row[1] not in found or row[2] != "NOT_FOUND":
                continue
            work = out_root / row[0]
            if not work.is_file() or work.is_symlink():
                continue
            debug = sd.POOL / "build-id" / f"{row[1]}.debug"
            staged = work.with_name(work.name + ".symbolized")
            error = sd.symbolize(work, debug, staged)
            if error:
                staged.unlink(missing_ok=True)
                row[2], row[3] = "UNSTRIP_FAILED", error
                continue
            os.replace(staged, work)
            row[2], row[3] = "SYMBOLIZED", str(debug)
            changed.append(f"{target}/{row[0]}")
        with tsv.open("w", newline="") as handle:
            csv.writer(handle, delimiter="\t", lineterminator="\n").writerows([header] + body)
    if apply:
        print(f"\nSymbolized in place ({len(changed)}):")
        for path in changed:
            print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
