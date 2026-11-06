#!/usr/bin/env python3
"""Render the comparison section of <img>/summary.md (everything before
"## Syscalls per library") as LaTeX in the style of the paper's companion
documents (swat4j_vs_sysjava.tex): 10pt article, Latin Modern, booktabs,
\\maketitle title, setup details in the table caption, run-in paragraph
headings. Writes <img>/summary.tex; the table is a self-contained table
environment that can be pasted into the paper.

Handles the subset of Markdown compare.py writes: a "# " title, "- **Key:**"
setup lines, one pipe table, and paragraphs with **bold** and `code`.

Usage: summary_tex.py <img>
"""
import itertools
import re
import sys
from pathlib import Path

run = Path(__file__).resolve().parent / sys.argv[1]
section = (run / "summary.md").read_text().split("\n## ")[0]

SPECIAL = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
           "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
           "^": r"\textasciicircum{}"}


def escape(text):
    return "".join(SPECIAL.get(c, c) for c in text)


def inline(text):
    """`code`, **bold**, "quotes" and SysJava to LaTeX."""
    parts = re.split(r"(`[^`]+`)", text)
    out = "".join(r"\texttt{" + escape(p[1:-1]) + "}" if p.startswith("`") else escape(p)
                  for p in parts)
    out = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", out)
    out = re.sub(r'"(.+?)"', r"``\1''", out)
    return re.sub(r"\bSysJava\b(?!\.)", r"\\sysname", out)


def table(lines, caption, label):
    rows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in lines]
    rule = next(r for r in rows if all(re.fullmatch(r":?-+:?", c) for c in r))
    rows = [r for r in rows if r is not rule]
    head, body = rows[0], rows[1:]
    align = "".join("r" if c.endswith(":") else "l" for c in rule)
    tex = [r"\begin{table}[H]", r"\centering", r"\caption{" + caption + "}",
           r"\label{" + label + "}", r"\begin{tabular}{" + align + "}",
           r"\toprule"]
    # "Group: column" headers become a two-level header with bold group names;
    # a column without a group keeps its bold name in the lower row.
    groups = [h.split(": ", 1) if ": " in h else ["", h] for h in head[1:]]
    if any(g[0] for g in groups):
        top, rules, i = [""], [], 2
        for name, run_ in itertools.groupby(g[0] for g in groups):
            span = len(list(run_))
            if name:
                top.append(r"\multicolumn{%d}{c}{\textbf{%s}}" % (span, inline(name)))
                rules.append(r"\cmidrule(lr){%d-%d}" % (i, i + span - 1))
            else:
                top += [""] * span
            i += span
        tex += [" & ".join(top) + r" \\", "".join(rules),
                " & ".join([r"\textbf{" + inline(head[0]) + "}"]
                           + [inline(g[1].capitalize()) if g[0] else r"\textbf{" + inline(g[1]) + "}"
                              for g in groups]) + r" \\"]
    else:
        tex.append(" & ".join(r"\textbf{" + inline(h) + "}" for h in head) + r" \\")
    tex.append(r"\midrule")
    tex += [" & ".join(inline(c) for c in r) + r" \\" for r in body]
    return tex + [r"\bottomrule", r"\end{tabular}", r"\end{table}"]


facts = dict(re.findall(r"^- \*\*([^:]+):\*\* (.+)$", section, re.M))
app = facts.get("Application", run.name)
setup = "; ".join(inline(v) for v in (
    "container " + facts["Container"] if "Container" in facts else "",
    facts.get("Distro", ""), facts.get("JDK", ""),
    "native libraries " + facts["Native libraries"] if "Native libraries" in facts else "")
    if v)
bound = "native methods and FFM downcalls" if "**FFM downcalls.**" in section \
    else "native methods"
caption = (f"Syscalls reached from the native libraries of {inline(app)}, with binding "
           f"recovery (analysis starts from the functions the {bound} are mapped to) "
           "and without (analysis starts from every function in the library)."
           + (" " + setup[0].upper() + setup[1:] + "." if setup else ""))
label = "tab:binding-" + re.sub(r"[^a-z0-9]+", "-", run.name.lower()).strip("-")

tex = [r"\documentclass[10pt]{article}", r"\usepackage[margin=2cm]{geometry}",
       r"\usepackage{booktabs}", r"\usepackage{float}", r"\usepackage{xspace}",
       r"\usepackage[T1]{fontenc}", r"\usepackage{lmodern}",
       r"\newcommand{\sysname}{SysJava\xspace}",
       r"\title{\sysname with and without Binding Recovery: " + inline(app) + "}",
       r"\author{}", r"\date{\vspace{-8ex}}", r"\begin{document}", r"\maketitle", ""]
block = []
for line in section.splitlines() + [""]:
    if line.startswith("|"):
        block.append(line)
        continue
    if block:
        tex += table(block, caption, label) + [""]
        block = []
    if line.startswith(("# ", "- ")) or not line.strip():
        continue                       # title and setup lines are used above
    m = re.match(r"^\*\*(.+?)\.?\*\* (.*)$", line)
    if m:                              # "**Heading.** text" -> run-in heading
        tex += [r"\paragraph*{" + inline(m.group(1)) + "}", inline(m.group(2)), ""]
    else:
        tex += [inline(line), ""]
tex.append(r"\end{document}")

out = run / "summary.tex"
out.write_text("\n".join(tex) + "\n")
print(out)
