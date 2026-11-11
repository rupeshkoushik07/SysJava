#!/usr/bin/env python3
"""Rebuild work/<image>/Dataset_symbolized/LIBS_<image> for the ten JDK 8 images from inputs/libs.tar.xz
(each distinct library file once, named by its sha256) and inputs/manifest.tsv.

Usage: python3 unpack_libs.py [work-dir]      (default: ./work)
"""
import csv, os, shutil, sys, tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = Path(sys.argv[1] if len(sys.argv) > 1 else HERE / "work").resolve()
store = WORK / "_store"
if not store.is_dir():
    with tarfile.open(HERE / "inputs" / "libs.tar.xz") as tf:
        tf.extractall(WORK / "_store_tmp")
    (WORK / "_store_tmp" / "libs").rename(store)
    (WORK / "_store_tmp").rmdir()
n = 0
for r in csv.DictReader(open(HERE / "inputs" / "manifest.tsv"), delimiter="\t"):
    p = WORK / r["img"] / "Dataset_symbolized" / f"LIBS_{r['img']}" / r["path"]
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists() or p.is_symlink():
        continue
    if r["kind"] == "link":
        os.symlink(r["target"], p)
    else:
        shutil.copy2(store / r["target"], p)
        os.chmod(p, 0o755)
    n += 1
print(f"{n} entries written under {WORK}")
