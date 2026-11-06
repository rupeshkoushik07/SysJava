#!/usr/bin/env python3
"""Compile <img>/summary.tex (from summary_tex.py) into <img>/summary.pdf, so
the PDF has the same look as the paper's LaTeX.

Uses pdflatex when it is installed, otherwise the texlive Docker image
($TEXLIVE_IMAGE, default texlive/texlive:latest-small). Builds in a temporary
directory, so no .aux/.log files are left next to the results.

Usage: summary_pdf.py <img>
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

run = Path(__file__).resolve().parent / sys.argv[1]
src = run / "summary.tex"
if not src.exists():
    raise SystemExit(f"{src} not found; run summary_tex.py {sys.argv[1]} first")

with tempfile.TemporaryDirectory() as tmp:
    shutil.copy(src, tmp)
    if shutil.which("pdflatex"):
        cmd = ["pdflatex"]
    else:
        cmd = ["docker", "run", "--rm", "-u", f"{os.getuid()}:{os.getgid()}",
               "-v", f"{tmp}:/w", "-w", "/w",
               os.environ.get("TEXLIVE_IMAGE", "texlive/texlive:latest-small"), "pdflatex"]
    for _ in range(2):                 # second pass settles the table number
        done = subprocess.run(cmd + ["-interaction=nonstopmode", "-halt-on-error",
                                     "summary.tex"], cwd=tmp, capture_output=True, text=True)
        if done.returncode:
            sys.exit(done.stdout[-2000:])
    shutil.copy(Path(tmp) / "summary.pdf", run / "summary.pdf")
print(run / "summary.pdf")
