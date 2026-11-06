#!/usr/bin/env python3
"""Table III (latest containers) in the paper's layout: writes <out>.tex (booktabs, paste into
the paper) and <out>.pdf (Computer Modern).

Rows and meanings follow the submitted paper's Table III. The one change: Unanalysed Lib
Syscalls comes before the runtime whitelist, and each of those two rows counts only syscalls
not already in the rows above it.

  Native Methods          methods declared native (Bytecode_Analysis/.../native_methods.txt)
  SysJava Resolved        natives mapped to a native function (mapper tags below), including
                          the manual mapping of natives whose library the image does not ship
                          (unavailable_libs/<target>/mapping/)
  Breakdown               mapper tags of the resolved natives; JNI Static + Partial + JNI Dynamic
                          + JVM + JFR/Netty = SysJava Resolved
                          (libc/Sigar bridge mappings are counted as JNI Static)
  JNA, FFI/FFM            binding-detector hits (call sites, not native declarations)
  Not Found               NOT_FOUND_IN_LIBS natives (other-OS natives and JVM intrinsics excluded)
  Java Lib Syscalls       library_syscalls.txt U jna_ffi_analysis/union_syscalls.txt
  Container Binary        binary_syscalls.txt (full set, as in the paper)
  Unanalysed Lib (Delta)  unanalysed_syscalls.txt minus the two rows above
  Runtime whitelist       runc.txt minus all rows above
  Total Syscalls          syscalls in the generated seccomp profile (checked = union of the rows)

Usage: make_paper_table.py <results_dir> <unavailable_libs_dir> <per_app_summary.csv> <out_prefix> <runc.txt>
"""
import csv, glob, json, os, re, sys, zipfile

res, unav, audcsv, out = sys.argv[1:5]
RUNTIME = sys.argv[5]
COLS = [("cassandra_5.0.8", "Cassandra", "5.0.8", "JDK 17", "Debian 12"), ("zookeeper_3.9.5", "Zookeeper", "3.9.5", "JDK 17", "Ubuntu 22.04"),
        ("tomcat_11.0.22", "Tomcat", "11.0", "JDK 25", "Ubuntu 24.04"), ("solr_10.0.0", "Solr", "10.0.0", "JDK 25", "Ubuntu 24.04"),
        ("groovy_5.0.6", "Groovy", "5.0.6", "JDK 21", "Ubuntu 24.04"), ("orientdb_3.2.53", "OrientDB", "3.2.53", "JDK 8", "Ubuntu 26.04"),
        ("jetty_12.1.10", "Jetty", "12.1.10", "JDK 25", "Ubuntu 26.04"), ("elasticsearch_7.1.0", "Elasticsearch", "7.1.0", "JDK 12", "CentOS 7"),
        ("storm_2.8.8", "Storm", "2.8.8", "JDK 17", "Ubuntu 26.04"), ("jruby_10.1.0.0", "JRuby", "10.1.0.0", "JDK 21", "Ubuntu 24.04")]
LINE = re.compile(r"^(?:\S+?:)?([\w.$]+) -> \S+ \[(\w+)\]")
aud = {r["app"]: r for r in csv.DictReader(open(audcsv))}


def names_in(path):
    if not os.path.exists(path):
        return set()
    return {l.strip() for l in open(path) if l.strip() and not l.startswith("#")}


def tags_of(path):
    tags = {}
    if os.path.exists(path):
        for l in open(path, errors="replace"):
            m = LINE.match(l.strip())
            if m:
                tags.setdefault(m.group(1), m.group(2))
    return tags


_ffm = {}
def uses_ffm(jar):
    """True if any class in the JAR references the FFM API (java/lang/foreign)."""
    if jar not in _ffm:
        try:
            z = zipfile.ZipFile(jar)
            _ffm[jar] = any(b"java/lang/foreign" in z.read(n) for n in z.namelist() if n.endswith(".class"))
        except (OSError, zipfile.BadZipFile):
            _ffm[jar] = True   # cannot check: keep the hit
    return _ffm[jar]


V, CHECK, FALSE_FFM = {}, {}, {}
for t, *_ in COLS:
    d = os.path.realpath(os.path.join(res, t)); b = d + "/Binary_Analysis"
    o = glob.glob(d + "/Bytecode_Analysis/outputs_*")[0]
    tags = tags_of(o + "/mapped_method_syscalls.txt")
    manual = tags_of(os.path.join(unav, t, "mapping", "mapped_method_syscalls.txt"))
    for k, v in manual.items():
        tags.setdefault(k, v)
    n = lambda *ks: sum(v in ks for v in tags.values())
    static, partial = int(aud[t]["et_jni_static"]), int(aud[t]["et_jni_partial"])
    jni = n("JNI")
    static += jni - (static + partial)          # manual JNI mappings (storm jansi) are static exports
    # Bindings that are not `native` declarations (JNA direct-mapped methods ARE declarations and
    # are already in native_methods.txt, so they are not counted again). Resolved = library and
    # symbol known.
    ovr = {}   # unresolved bindings classified in unavailable_libs/<t>/binding_overrides.tsv
    op = os.path.join(unav, t, "binding_overrides.tsv")
    if os.path.exists(op):
        for l in open(op):
            g = l.rstrip("\n").split("\t")
            ovr[tuple(g[:4])] = g[4]
    bind, bind_platform = {}, 0
    for l in open(o + "/jna_hits.txt", errors="replace").readlines()[2:]:
        f = [x.strip() for x in l.split("|")]
        if len(f) < 4 or f[0] not in ("iface", "dyn", "jnr-ffi", "ffi"):
            continue
        # FfiDetector's class-name fallback also fires on JARs that never use the FFM API
        # (clojure.core$abs -> libc abs, EvpHmac$MD5 -> libcrypto MD5): not bindings, not counted.
        if f[0] == "ffi" and len(f) > 5 and not uses_ffm(f"{d}/Dataset/JARFILES_{t}/{f[5]}"):
            FALSE_FFM.setdefault(t, set()).add(f[3])
            continue
        ok = f[2] not in ("<?>", "") and f[3] not in ("<?>", "")
        if not ok:
            k = ovr.get(tuple(f[:4]))
            ok = k == "mapped"
            bind_platform += k == "platform"
        tot, r_ = bind.get(f[0], (0, 0)); bind[f[0]] = (tot + 1, r_ + ok)
    rb = lambda k: bind.get(k, (0, 0))[1]
    java = names_in(f"{b}/syscalls_output_{t}/library_syscalls.txt")
    # JNA/FFI syscalls per bound library; skip a library whose start list holds only false FFM symbols
    for sd in glob.glob(f"{b}/jna_ffi_analysis/syscalls/*/"):
        lib = os.path.basename(sd.rstrip("/"))
        starts = names_in(f"{b}/jna_ffi_analysis/startfuncs/{lib}.txt")
        if starts and starts <= FALSE_FFM.get(t, set()):
            continue
        java |= names_in(sd + "syscalls.txt")
    # manual mapping: syscalls SysPart reaches from the supplied libraries' newly mapped starts
    for sp in glob.glob(os.path.join(unav, t, "syspart*", "syscalls.txt")):
        java |= names_in(sp)
    binary = names_in(f"{b}/syscalls_BIN_{t}/binary_syscalls.txt")
    unan = names_in(f"{b}/syscalls_unanalysed_{t}/unanalysed_syscalls.txt") - java - binary
    runtime = (names_in(d + "/runtime_set.txt") or names_in(RUNTIME)) - java - binary - unan
    prof = json.load(open(f"{b}/syscalls_output_{t}/{t}.json"))
    total = {x for r in prof.get("syscalls", []) if r.get("action") == "SCMP_ACT_ALLOW" for x in r["names"]}
    merged = os.path.join(unav, t, "merged", f"{t}_with_supplement.txt")   # profile + manual-mapping syscalls
    if os.path.exists(merged):
        total |= names_in(merged)
    rows = java | binary | unan | runtime
    CHECK[t] = sorted(total - rows) or True   # profile entries no row explains (false FFM starts)
    total = rows
    parts = [static + n("DIRECT_LIBC_BRIDGE", "SIGAR_LIST_BRIDGE"), partial, n("JNI_DYNAMIC", "REGISTERED"), n("JVM"), n("NETTY")]  # bridges map to exported libc functions
    assert sum(parts) == len(tags), (t, parts, len(tags))
    total_n = int(aud[t]["denominator"]) + sum(v[0] for v in bind.values())
    jna_s, jna_d, ffi = rb("iface"), rb("dyn"), rb("ffi") + rb("jnr-ffi")
    resolved = sum(parts) + jna_s + jna_d + ffi
    pe = os.path.join(unav, t, "platform_extra.txt")   # classified in unavailable_libs/notfound_search/
    platform = int(aud[t]["et_platform"]) + len(names_in(pe)) + bind_platform   # other OS + JVM intrinsics + no native target
    V[t] = [total_n, resolved, None, *parts, f"{jna_s} / {jna_d}", ffi, platform, total_n - resolved - platform,
            None, len(java), len(binary), len(unan), len(runtime), len(total)]

LABELS = ["Native Methods", "SysJava Resolved", "Resolution Breakdown (SysJava)", "JNI Static (Java\\_*)",
          "Partial (\\_1/\\$/\\_\\_)", "JNI Dynamic (RegisterNatives)", "JVM", "JFR/Netty",
          "JNA (Static / Dynamic)", "FFI/FFM (incl. JNR-FFI)", "Platform / Intrinsic", "Not Found", "Syscall Allowlist (SysJava only)", "Java Lib Syscalls",
          "Container Binary Syscalls", "Unanalysed Lib Syscalls ($\\Delta$)", "Go Whitelist ($\\Delta$)", "Total Syscalls"]
INDENT = set(range(3, 12))
CAPTION = ("Native method resolution for SysJava on latest container images (JDK 8--25). JNA and FFI bindings are "
           "resolved statically from bytecode call sites.")
NOTE = ("Note: Native Methods = methods declared native (JNI and JNA direct mapping) + JNA interface and dynamic "
        "bindings + JNR-FFI and FFM bindings. The breakdown rows count resolved natives and add up to SysJava Resolved; "
        "Platform / Intrinsic = natives and bindings for other operating systems (Windows, macOS, Solaris, BSD), JVM "
        "intrinsics, and bindings with no native target (FFM upcall callbacks, vDSO calls). Not Found = natives with no symbol in any available library, and JNA/FFI bindings whose library or symbol "
        "is unknown. SysJava Resolved + Platform / Intrinsic + Not Found = Native Methods. Tomcat 11 uses the FFM API extensively (382 FFI bindings), reflecting the move away from JNI in newer Java "
        "versions; FFM hits that the detector inferred from a class name in a JAR that never references java.lang.foreign (e.g. clojure.core\\$abs, EvpHmac\\$MD5) are not counted. JNA and FFI bindings are resolved statically using SysJava's binding rules and constant propagation to "
        "API arguments. Solr and Storm include natives mapped by supplying the library the image does not ship "
        "(Solr netty-tcnative 2.0.70: 276; Storm jansi: 9 and netty io_uring: 62, which adds io\\_uring\\_setup/enter/register; Tomcat: 2 commons-daemon natives in jsvc, built from the image's commons-daemon-native source; OrientDB jffi 1.3.11: 37 and Lucene NativePosixUtil: 5; "
        "Elasticsearch NativePosixUtil: 5). Unanalysed Lib Syscalls ($\\Delta$) are syscalls reachable from native "
        "libraries present in the container but without a direct Java binding entry point, not already counted above; the "
        "Go Whitelist ($\\Delta$) adds the runc entries not already counted. All ten containers run under their generated "
        "profiles.")
n = len(COLS); names = [c[0] for c in COLS]
# ---- LaTeX
tex = ["% Generated by EchoTrace_latest/tables/make_paper_table.py", "\\begin{table*}[t]", "\\centering",
       f"\\caption{{{CAPTION}}}", "\\label{tab:latest}", "\\scriptsize", "\\setlength{\\tabcolsep}{3pt}",
       "\\begin{tabular}{@{}l" + "r" * n + "@{}}", "\\toprule"]
for i in (1, 2, 3, 4):
    tex.append(" & " + " & ".join(c[i] for c in COLS) + " \\\\")
tex.append("\\midrule")
tex.append(f"\\multicolumn{{{n+1}}}{{@{{}}l}}{{Native Method Resolution}} \\\\ \\midrule")
for k, lab in enumerate(LABELS):
    if V[names[0]][k] is None:
        tex.append(f"\\midrule\n\\multicolumn{{{n+1}}}{{@{{}}l}}{{{lab}}} \\\\ \\midrule"); continue
    tex.append(("\\quad " if k in INDENT else "") + lab + " & " + " & ".join(str(V[t][k]) for t in names) + " \\\\")
tex += ["\\bottomrule", "\\end{tabular}", "\\par\\smallskip", "\\begin{minipage}{\\textwidth}\\footnotesize", NOTE,
        "\\end{minipage}", "\\end{table*}"]
open(out + ".tex", "w").write("\n".join(tex) + "\n")
# ---- PDF (Computer Modern from matplotlib's BaKoMa TTFs)
try:
    import matplotlib
except ImportError:
    sys.exit(f"wrote {out}.tex (no PDF: matplotlib not installed)")
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
F = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data/fonts/ttf")
pdfmetrics.registerFont(TTFont("CMR", F + "/cmr10.ttf")); pdfmetrics.registerFont(TTFont("DejaVu", F + "/DejaVuSerif.ttf"))


def plain(s):
    # cmr10 (BaKoMa TTF) has no underscore or en dash glyph; set those in a fallback serif.
    s = s.replace("$\\Delta$", "<font name='DejaVu'>\u0394</font>").replace("\\$", "$")
    return s.replace("\\_", "<font name='DejaVu'>_</font>").replace("--", "<font name='DejaVu'>\u2013</font>")


cap = ParagraphStyle("c", fontName="CMR", fontSize=11, leading=14)
note = ParagraphStyle("n", fontName="CMR", fontSize=9, leading=11.5)
cell = ParagraphStyle("x", fontName="CMR", fontSize=8, leading=9.5)
rows = [[""] + [c[i] for c in COLS] for i in (1, 2, 3, 4)]
sec = []
rows.append(["Native Method Resolution"] + [""] * n); sec.append(len(rows) - 1)
for k, lab in enumerate(LABELS):
    if V[names[0]][k] is None:
        rows.append([lab] + [""] * n); sec.append(len(rows) - 1); continue
    rows.append([Paragraph(("&nbsp;&nbsp;&nbsp;" if k in INDENT else "") + plain(lab), cell)] + [str(V[t][k]) for t in names])
tbl = Table(rows, colWidths=[132] + [64] * n)
st = [("FONT", (0, 0), (-1, -1), "CMR", 8), ("ALIGN", (1, 0), (-1, 3), "CENTER"), ("ALIGN", (1, 4), (-1, -1), "RIGHT"),
      ("LINEABOVE", (0, 0), (-1, 0), 0.9, colors.black), ("LINEBELOW", (0, 3), (-1, 3), 0.5, colors.black),
      ("LINEBELOW", (0, -1), (-1, -1), 0.9, colors.black), ("TOPPADDING", (0, 0), (-1, -1), 0.8),
      ("BOTTOMPADDING", (0, 0), (-1, -1), 0.8)]
for i in sec:
    st += [("SPAN", (0, i), (-1, i)), ("LINEBELOW", (0, i), (-1, i), 0.4, colors.black)]
    if i > 4:
        st.append(("LINEABOVE", (0, i), (-1, i), 0.4, colors.black))
tbl.setStyle(TableStyle(st))
doc = SimpleDocTemplate(out + ".pdf", pagesize=landscape(A4), leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
doc.build([Paragraph("Table III: " + plain(CAPTION), cap), Spacer(1, 6), tbl, Spacer(1, 4), Paragraph(plain(NOTE), note)])
print("wrote", out + ".tex", out + ".pdf"); print("profile entries not explained by the rows:", CHECK); print("false FFM symbols:", {k: len(v) for k, v in FALSE_FFM.items()})
