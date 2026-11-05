#!/usr/bin/env python3
"""Build the debug-symbol recovery report (PDF).

Reads Final_results_echotrace/<target>/Dataset_symbolized/symbols.tsv (from
symbolize_dataset.py) and Final_results_echotrace/symbolized_comparison.tsv
(from compare_symbolized.py) and writes
Final_results_echotrace/debug_symbols_report.pdf: the method, the before/after
effect on SysPart call graphs, and every ELF whose symbols could not be found
with the reason.

Requires reportlab (pip install reportlab).
"""

from __future__ import annotations

import csv
import datetime
import re
from collections import Counter, defaultdict
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

RESULTS_ROOT = Path(__file__).resolve().parent.parent / "Final_results_echotrace"
OUT = RESULTS_ROOT / "debug_symbols_report.pdf"
RESOLVED = {"SYMBOLIZED"}

JDK_NAMES = re.compile(
    r"^lib(jvm|java|net|nio|zip|awt.*|jli|verify|management.*|sctp|sunec|jaas.*|fontmanager|jimage|"
    r"extnet|prefs|attach|j2pkcs11|instrument|dt_socket|jdwp|lcms|mlib_image|jawt|jsound|splashscreen|"
    r"javajpeg|rmi|unpack|saproc|hprof|npt|j2gss|j2pcsc|jsig|syslookup|dt_shmem|le|freetype)\.so$")
VENDOR = re.compile(r"snappy|lz4|sigar|jnidispatch|netty|rocksdb|zstd|jffi|jansi|tcnative|Corretto|"
                    r"icmp|hadoop|NativePosix|^controller$|libMl|boost|hdfspp|nativetask|pipes-|wordcount")

REASONS = {
    "jdk": ("JDK built by its vendor",
            "Temurin / Corretto / Docker-official OpenJDK tarball builds. The vendors strip these "
            "libraries and do not publish separate debug files; the distro OpenJDK -dbg packages "
            "are a different build, so their Build IDs never match."),
    "vendor": ("Third-party native code shipped inside JARs or app tarballs",
               "JNI libraries bundled in Maven artifacts (snappy-java, lz4-java, sigar, JNA, netty, "
               "RocksDB, zstd-jni, jffi, jansi, tcnative, ACCP) and Elastic's ML/Hadoop binaries. They "
               "are built by the project's CI, stripped, and no symbol server or package carries them."),
    "drift": ("Container image changed since extraction",
              "The dataset copy has a Build ID that no longer exists in the running container (e.g. "
              "storm_2.4.0 binaries were captured from et_storm-2.4.0-temurin8_latest). The owning "
              "package version cannot be read, so the archive lookup cannot be pinned."),
    "distro": ("Distro package, debug file not published or withdrawn",
               "The owning distro package was identified, but neither debuginfod nor the archived "
               "dbgsym/-dbg package at that exact version contains this Build ID (security rebuilds "
               "whose ddebs Launchpad expired, Debian packages that never shipped -dbgsym, or a "
               "non-distro build such as gosu/tini)."),
    "nobid": ("No GNU Build ID",
              "Without a Build ID there is no key to look up a debug file safely, and a guessed "
              "match could silently attach wrong symbols. Typical of Go binaries and hand-built tools."),
    "truncated": ("Dataset copy truncated, no intact original found",
                  "The extracted file stops partway (section headers past EOF). No byte-identical "
                  "full copy exists in the container, on the host, or in any container JAR."),
    "unstrip": ("Debug file found but merge failed",
                "eu-unstrip rejected the pair; the ELF is kept as extracted."),
}


def classify(path: str, target: str, status: str, detail: str) -> str:
    name = Path(path).name
    if status == "NO_BUILD_ID":
        return "nobid"
    if status == "TRUNCATED":
        return "truncated"
    if status == "UNSTRIP_FAILED":
        return "unstrip"
    if JDK_NAMES.match(name) or "JDK" in path and "_LIBS" in path:
        return "jdk"
    if VENDOR.search(name):
        return "vendor"
    if target == "storm_2.4.0" and path.startswith("BINARIES_"):
        return "drift"
    return "distro"


def load_symbols() -> list[dict]:
    rows = []
    for tsv in sorted(RESULTS_ROOT.glob("*/Dataset_symbolized/symbols.tsv")):
        target = tsv.parent.parent.name
        with tsv.open() as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                row["target"] = target
                rows.append(row)
    return rows


def load_comparison() -> list[dict]:
    path = RESULTS_ROOT / "symbolized_comparison.tsv"
    if not path.is_file():
        return []
    with path.open() as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def as_int(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def main() -> int:
    symbols = load_symbols()
    comparison = load_comparison()

    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9.5, leading=13)
    small = ParagraphStyle("small", parent=body, fontSize=7.5, leading=9.5)
    mono = ParagraphStyle("mono", parent=small, fontName="Courier", fontSize=7, leading=8.5)
    h1, h2 = styles["Heading1"], styles["Heading2"]

    def table(data, widths, header_bg=colors.HexColor("#2b3a55"), font=7.5):
        t = Table(data, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), header_bg),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), font),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#b8bfcc")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f4f8")]),
            ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ]))
        return t

    status_counts = Counter(r["status"] for r in symbols)
    stripped = [r for r in symbols if r["status"] != "HAS_SYMTAB"]
    missing = [r for r in stripped if r["status"] not in RESOLVED]
    for r in missing:
        r["reason"] = classify(r["path"], r["target"], r["status"], r.get("detail", ""))
    reason_counts = Counter(r["reason"] for r in missing)

    story = [Paragraph("EchoTrace: Debug-Symbol Recovery for SysPart Call Graphs", styles["Title"]),
             Paragraph(f"Generated {datetime.date.today():%d %B %Y} &middot; "
                       f"{len({r['target'] for r in symbols})} container targets &middot; "
                       f"{len(symbols)} ELF files", body),
             Spacer(1, 6 * mm)]

    # ------------------------------------------------------------- summary
    story.append(Paragraph("1. Summary", h1))
    analysed = [c for c in comparison if c["functions_after"] != ""]
    fz_b = sum(as_int(c["fuzzy_before"]) for c in analysed)
    fz_a = sum(as_int(c["fuzzy_after"]) for c in analysed)
    fn_b = sum(as_int(c["functions_before"]) for c in analysed)
    fn_a = sum(as_int(c["functions_after"]) for c in analysed)
    revived = sum(1 for c in analysed if as_int(c["functions_before"]) == 0 and as_int(c["functions_after"]) > 0)
    story.append(Paragraph(
        f"SysPart names a function only when the ELF that contains it carries a symbol table. Of the "
        f"{len(symbols)} ELF files extracted from the {len({r['target'] for r in symbols})} containers, "
        f"<b>{len(stripped)}</b> were stripped. Debug symbols were recovered and merged for "
        f"<b>{status_counts['SYMBOLIZED']}</b> of them; <b>{len(missing)}</b> remain without symbols, "
        f"for the reasons listed in section 5.", body))
    if analysed:
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph(
            f"All {len(analysed)} SysPart analyses were re-run on the symbolized ELFs with the original "
            f"start functions. Unnamed functions (<font face='Courier'>fuzzyfunc-0x...</font>) went from "
            f"<b>{fz_b:,}</b> of {fn_b:,} call-graph functions to <b>{fz_a:,}</b> of {fn_a:,}. "
            f"<b>{revived}</b> analyses that previously produced an empty call graph now complete.", body))
    story.append(Spacer(1, 3 * mm))
    story.append(table([["Outcome", "ELFs"]] + [[k, str(v)] for k, v in sorted(status_counts.items())],
                       [70 * mm, 25 * mm], font=8.5))

    # -------------------------------------------------------------- method
    story.append(Paragraph("2. How the symbols are found", h1))
    steps = [
        ("Inventory", "Every ELF under <i>Dataset/LIBS_*</i> and <i>Dataset/BINARIES_*</i> is read for its "
         "GNU Build ID and whether it has a <font face='Courier'>.symtab</font>. Working on the extracted "
         "dataset, not the whole container rootfs, means only what the analysis loads is fetched."),
        ("Repair truncated copies", "41 dataset ELFs (libjvm.so in every target, libcrypto, rocksdb, "
         "python2.7, runc...) were cut off mid-file, so SysPart could not parse them at all. An intact "
         "original is accepted only if the truncated copy is an exact byte prefix of it; candidates are "
         "searched in the running <i>et_&lt;target&gt;</i> container, on the host (runc), and inside "
         "container JARs for JNI libraries the JVM unpacked to a temp file."),
        ("Fix wrong-platform JNI builds", "JAR bundles ship one native build per platform and extraction "
         "sometimes kept the wrong one (an i386 libjnidispatch.so, S/390 zstd-jni and jffi, an AArch64 "
         "lz4-java, FreeBSD/musl snappy builds needing libc.so.7 or libm.so.2). Egalito rejects or crashes "
         "on these. They are replaced with the Linux x86-64 glibc build of the same library from the same "
         "JAR in the container."),
        ("Complete dependencies", "DT_NEEDED libraries absent from the mirror (tomcat_7.0 had no container "
         "libc at all; ld-linux, libseccomp and others were missing in most targets) are copied from the "
         "container's library directories into <i>_container_deps/</i> and symbolized like everything else. "
         "Otherwise Egalito silently loads the host's copy, and the call graph describes the host."),
        ("debuginfod", "Each Build ID is requested from the public debuginfod federation (Ubuntu, Debian, "
         "Fedora, CentOS, Rocky, openSUSE, elfutils). Results are pooled in "
         "<i>artifacts/all-running-containers/debug-symbols/build-id/</i> and re-used across targets."),
        ("Exact-version distro packages", "For Build IDs debuginfod no longer serves (older point "
         "releases), the owning package and its exact installed version are read from the container "
         "with <font face='Courier'>dpkg-query -S</font> / <font face='Courier'>rpm -qf</font> (read-only), "
         "and the matching <i>-dbgsym</i>, <i>-dbg</i> or <i>libc6-dbg</i> package is downloaded from "
         "snapshot.debian.org, Launchpad (Ubuntu .ddeb) or debuginfo.centos.org. Sibling "
         "<i>et_&lt;app&gt;*</i> containers are consulted too, because some datasets mix images."),
        ("Verification", "A debug file is used only if its own GNU Build ID equals the stripped ELF's. "
         "This makes wrong-version symbols impossible, whichever source supplied the file."),
        ("Merge", "<font face='Courier'>eu-unstrip</font> merges the debug file into a copy of the ELF, then "
         "<font face='Courier'>objcopy --strip-debug</font> drops DWARF again. The result is the original "
         "code plus a restored symbol table, written to <i>Dataset_symbolized/</i>. The original "
         "<i>Dataset/</i> is never modified."),
        ("Re-run SysPart", "<i>scripts/rerun_syspart_symbolized.sh</i> repeats every recorded analysis "
         "with the same start functions into <i>Binary_Analysis_symbolized/</i>. SONAME links that "
         "extraction dropped are recreated first, so dependencies such as libc.so.6 resolve to the "
         "container's copy rather than the host's."),
    ]
    story.append(table([["Step", "What is done and why"]] +
                       [[Paragraph(f"<b>{a}</b>", small), Paragraph(b, small)] for a, b in steps],
                       [32 * mm, 140 * mm]))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "Installing dbgsym packages inside the running containers (<i>CONTAINER_FALLBACK=1</i>) is "
        "supported but was not used: it modifies the evaluation containers, and the archive download "
        "reaches the same packages without touching them.", body))

    # ------------------------------------------------- data-quality findings
    story.append(Paragraph("3. Problems found in the original results", h1))
    for text in [
        "<b>Truncated ELFs.</b> 41 dataset files were incomplete, so their original SysPart runs were "
        "empty or analysed nothing; libjvm.so had never actually been analysed in any target.",
        "<b>Host libc used instead of container libc.</b> Extraction keeps only versioned files "
        "(libc-2.31.so) and drops SONAME links (libc.so.6). SysPart then could not find libc.so.6 in the "
        "mirror and silently loaded the host's. The re-run recreates the links.",
        "<b>Wrong-platform JNI libraries.</b> cassandra_5.0.6-bookworm and solr_8.7.0 contained i386, "
        "AArch64, S/390 and FreeBSD builds of JAR-bundled libraries under the names SysPart analysed.",
        "<b>Missing dependencies.</b> DT_NEEDED libraries absent from the mirror were resolved from the "
        "host by Egalito, so parts of the original call graphs were computed on host code.",
        "<b>Mixed images in storm_2.4.0.</b> Several BINARIES (cut, id, chown...) come from the Ubuntu "
        "image et_storm-2.4.0-temurin8_latest, not the Debian storm:2.4.0 image.",
        "<b>Null-symbol crash.</b> Egalito dereferences a null symbol list in PLT parsing when a "
        "stripped libc is loaded (documented in artifacts/cassandra_5.0.6-bookworm/diagnosis.txt). "
        "Restoring libc's symbol table avoids it.",
    ]:
        story.append(Paragraph("&bull; " + text, body))
        story.append(Spacer(1, 1.5 * mm))

    # ------------------------------------------------------ before / after
    if comparison:
        story.append(PageBreak())
        story.append(Paragraph("4. Effect on SysPart results", h1))
        per_target = defaultdict(lambda: Counter())
        for c in comparison:
            t = per_target[c["target"]]
            t["elfs"] += 1
            if c["functions_after"] == "":
                t["not_rerun"] += 1
                continue
            for key in ("functions_before", "fuzzy_before", "functions_after", "fuzzy_after"):
                t[key] += as_int(c[key])
            t["revived"] += int(as_int(c["functions_before"]) == 0 and as_int(c["functions_after"]) > 0)

        def pct(a, b):
            return f"{100 * a / b:.1f}%" if b else "-"
        data = [["Target", "ELFs", "Unnamed before", "Unnamed after", "Empty graphs fixed", "Not re-run"]]
        for target, t in sorted(per_target.items()):
            data.append([target, t["elfs"],
                         f"{t['fuzzy_before']:,} ({pct(t['fuzzy_before'], t['functions_before'])})",
                         f"{t['fuzzy_after']:,} ({pct(t['fuzzy_after'], t['functions_after'])})",
                         t["revived"], t["not_rerun"]])
        story.append(table(data, [42 * mm, 12 * mm, 38 * mm, 38 * mm, 24 * mm, 18 * mm], font=8))
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph("Per-ELF numbers, including which modules the remaining unnamed functions "
                               "belong to, are in <i>Final_results_echotrace/symbolized_comparison.tsv</i>.",
                               body))
        worst = sorted((c for c in comparison if c["functions_after"] != "" and as_int(c["fuzzy_after"]) > 0),
                       key=lambda c: -as_int(c["fuzzy_after"]))[:25]
        if worst:
            story.append(Paragraph("Largest remaining unnamed sets", h2))
            story.append(table(
                [["Target", "ELF", "Before", "After", "Where the unnamed functions are"]] +
                [[c["target"], c["elf"], c["fuzzy_before"], c["fuzzy_after"],
                  Paragraph(c["remaining_fuzzy_by_module"], small)] for c in worst],
                [34 * mm, 38 * mm, 14 * mm, 14 * mm, 72 * mm]))

    # ------------------------------------------------------- missing list
    story.append(PageBreak())
    story.append(Paragraph("5. ELFs whose debug symbols could not be found", h1))
    story.append(Paragraph(
        f"{len(missing)} stripped ELFs remain without symbols. Each is classified by cause below; "
        f"the justification explains why no source exists or why it is unsafe to use one.", body))
    story.append(Spacer(1, 2 * mm))
    story.append(table([["Cause", "ELFs", "Justification"]] +
                       [[Paragraph(f"<b>{REASONS[k][0]}</b>", small), str(v), Paragraph(REASONS[k][1], small)]
                        for k, v in reason_counts.most_common()],
                       [45 * mm, 12 * mm, 115 * mm]))
    for key, _ in reason_counts.most_common():
        rows = sorted((r for r in missing if r["reason"] == key), key=lambda r: (r["target"], r["path"]))
        story.append(Paragraph(f"{REASONS[key][0]} ({len(rows)})", h2))
        story.append(table(
            [["Target", "ELF (dataset path)", "GNU Build ID"]] +
            [[r["target"], Paragraph(r["path"], mono), Paragraph(r["gnu_build_id"] or "-", mono)] for r in rows],
            [34 * mm, 82 * mm, 56 * mm]))

    # --------------------------------------------------------- reproduce
    story.append(Paragraph("6. Reproducing", h1))
    for cmd in ["python3 scripts/symbolize_dataset.py [target ...]",
                "PHASE=light JOBS=4 JOB_MEM_GB=12 scripts/rerun_syspart_symbolized.sh",
                "PHASE=heavy JOBS=1 JOB_MEM_GB=55 scripts/rerun_syspart_symbolized.sh",
                "python3 scripts/compare_symbolized.py",
                "python3 scripts/debug_symbols_report.py"]:
        story.append(Paragraph(cmd, ParagraphStyle("cmd", parent=mono, fontSize=8.5, leading=11)))

    def footer(canvas, doc):
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(A4[0] - 15 * mm, 10 * mm, f"EchoTrace debug-symbol recovery · page {doc.page}")

    SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
                      topMargin=15 * mm, bottomMargin=16 * mm,
                      title="EchoTrace Debug-Symbol Recovery").build(story, onFirstPage=footer, onLaterPages=footer)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
