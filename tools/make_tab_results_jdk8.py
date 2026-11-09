#!/usr/bin/env python3
"""tab:results (Table II, primary JDK 8 set) in the submitted paper's row layout, from the rebuilt
JDK 8 images (Final_results_JDK8/<app>-jdk8-buster). Writes <out>.tex and <out>.md.

  JNI Total Natives         methods declared native (outputs_<t>/native_methods.txt), as in the
                            audit's denominator; JNA/JNR bindings are not declarations (see note)
  SysJava rows              mapper tags in mapped_method_syscalls.txt (same rules as tab:latest):
                            Static + Partial + JNI Dynamic + JVM + JFR/Netty = SysJava Resolved;
                            Resolved + Platform/Intrinsic + Not Found = JNI Total Natives
  SWAT4J rows               SWAT4J's own JNI mapping of the native methods its own JTracer finds, with its
                            repository's JNI_thirdparty/ libraries as in the original setup
                            (swat4j/outputs/mapping/<app>.tsv,
                            count_own_mapping.py); NOT SysJava's native_methods.txt (decision 2026-11-09)
  Java Lib Syscalls         library_syscalls.txt U syscalls of the JNA/JNR-bound libraries (libraries
                            bound only by false FFM hits are left out: JDK 8 has no FFM API)
  Container Binary          binary_syscalls.txt U extra_components/*/syscalls.txt (ES ML controller)
  Go Whitelist (Delta)      runc.txt entries not in the two rows above
  Unmapped Lib (Delta)      unanalysed_syscalls.txt entries not in any row above
  Total Syscalls            union of the rows; checked against the generated profile
  SWAT4J Java Lib           SWAT4J static allowlist (JTracer + binary_analyser.py, unmodified SWAT4J, repository
                            libraries: swat4j/outputs/static/syscalls/)
  Dynamic capture           sysdig capture (Dynamic_Analysis/sysdig_outputs_<t>/): distinct .so paths
                            opened, distinct executed binaries, distinct JARs opened; libraries with
                            mapped natives that SysPart analysed (syscalls_output_<t>/<lib>/)

Usage: make_tab_results.py <per_app_summary.csv> <out_prefix>   (RESULTS=<results dir>, SWAT4J_OUTPUTS=<dir> to read another run)
A column whose pipeline has not finished ("stage done: finished") shows "pending".
"""
import csv, glob, json, os, re, sys

ART = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.environ.get("RESULTS", ART + "/2_swat4j_vs_sysjava/sysjava_results")
SWO = os.environ.get("SWAT4J_OUTPUTS", ART + "/swat4j/outputs")
SW, SWM, SWD = SWO + "/static/syscalls", SWO + "/mapping", SWO + "/dynamic"
RUNC = ART + "/2_swat4j_vs_sysjava/runc.txt"
UNAV = ART + "/2_swat4j_vs_sysjava/manual_mapping"
COLS = [("zookeeper_3.4.14", "zookeeper", "Zookeeper", "3.4.14"), ("tomcat_7.0", "tomcat", "Tomcat", "7.0"),
        ("cassandra_3.0.29", "cassandra", "Cassandra", "3.0.29"), ("jetty_9.4.51", "jetty", "Jetty", "9.4.51"),
        ("storm_2.4.0", "storm", "Storm", "2.4.0"), ("orientdb_3.2.19", "orientdb", "OrientDB", "3.2.19"),
        ("elasticsearch_7.5.2", "elasticsearch", "Elasticsearch", "7.5.2"), ("solr_8.7.0", "solr", "Solr", "8.7.0"),
        ("groovy_4.0.0", "groovy", "Groovy", "4.0.0"), ("jruby_9.4.2.0", "jruby", "JRuby", "9.4.2.0")]
LINE = re.compile(r"^(?:\S+?:)?([\w.$]+) -> \S+ \[(\w+)\]")
ALIASES = {"pread": "pread64", "pwrite": "pwrite64"}
aud = {r["app"]: r for r in csv.DictReader(open(sys.argv[1]))}
out = sys.argv[2]


def names_in(path):
    if not os.path.exists(path):
        return set()
    return {ALIASES.get(l.split()[0], l.split()[0]) for l in open(path, errors="replace")
            if l.strip() and not l.startswith("#")}


def tags_of(path):
    tags = {}
    for l in open(path, errors="replace"):
        m = LINE.match(l.strip())
        if m:
            tags.setdefault(m.group(1), m.group(2))
    return tags


LABELS = ["Native Method Resolution", "JNI Total Natives", "SysJava Resolved", "JNI Static (Java\\_*)",
          "Partial (\\_1/\\$/\\_\\_)", "JNI Dynamic (RegisterNatives)", "JVM", "JFR/Netty", "Platform / Intrinsic",
          "Not Found", "SWAT4J Natives Found (JTracer)", "SWAT4J Resolved", "SWAT4J JNI Static (Java\\_*)", "JNI Partial/Heuristic", "JVM Source Code",
          "Not Found ", "Syscall Allowlist (SysJava only)", "Java Lib Syscalls", "Container Binary Syscalls",
          "Go Whitelist ($\\Delta$)", "Unmapped Lib Syscalls ($\\Delta$)", "Total Syscalls",
          "SWAT4J Syscall Comparison", "SWAT4J Java Lib Syscalls", "SWAT4J Dynamic Syscalls",
          "SWAT4J Total (Static $\\cup$ Dynamic)", "SysJava $\\cap$ SWAT4J", "SysJava only", "SWAT4J only",
          "Dynamic Capture Artefacts", "Libraries Loaded",
          "Binaries Loaded", "JARs Loaded", "Directly Mapped Libraries Analysed"]
SECTIONS = {0, 16, 22, 29}
INDENT = {3, 4, 5, 6, 7, 8, 9, 12, 13, 14, 15}

V, CHECK = {}, {}
for folder, app, *_ in COLS:
    t = folder + "-jdk8-buster"
    d = f"{RES}/{t}"; b = d + "/Binary_Analysis"
    log = d + "/pipeline_run.log"
    done = os.path.exists(log) and "stage done: finished" in open(log, errors="replace").read().splitlines()[-1]
    col = ["pending"] * len(LABELS)
    sw_java = names_in(f"{SW}/{app}.txt")
    sw_dyn = names_in(f"{SWD}/{app}_result.txt")
    sw_all = sw_java | sw_dyn
    col[23] = len(sw_java) if sw_java else "pending"
    col[24] = len(sw_dyn) if sw_dyn else "pending"
    col[25] = len(sw_all) if sw_java and sw_dyn else "pending"
    if not done or t not in aud:
        V[t] = col; continue
    a = aud[t]
    o = glob.glob(d + "/Bytecode_Analysis/outputs_*")[0]
    tags = tags_of(o + "/mapped_method_syscalls.txt")
    manual = f"{UNAV}/{t}/mapping/mapped_method_syscalls.txt"
    if os.path.exists(manual):
        for k, v in tags_of(manual).items():
            if v != "NOT_FOUND":
                tags.setdefault(k, v)
    n = lambda *ks: sum(v in ks for v in tags.values())
    static, partial = int(a["et_jni_static"]), int(a["et_jni_partial"])
    static += n("JNI") - (static + partial)   # manual JNI mappings (supplied libraries) are static exports
    parts = [static + n("DIRECT_LIBC_BRIDGE", "SIGAR_LIST_BRIDGE"), partial, n("JNI_DYNAMIC", "REGISTERED"), n("JVM"), n("NETTY", "NETTY_FUZZY")]
    resolved = sum(parts)
    assert resolved == len(tags), (t, parts, len(tags))
    total_n = int(a["denominator"])
    platform = int(a["et_platform"]) + int(a["et_intrinsic"]) + len(names_in(f"{UNAV}/{t}/platform_extra.txt"))
    # SWAT4J: its own JTracer list, one row per method with the rule that mapped it (count_own_mapping.py)
    st = [l.rstrip("\n").split("\t")[1] for l in list(open(f"{SWM}/{app}.tsv"))[1:]]
    c = lambda k: st.count(k)
    sw = [len(st), len(st) - c("UNMAPPED"), c("Java_XXX"), c("NETTY_HEURISTIC"), c("JVM_XXX"), c("UNMAPPED")]

    # false FFM hits (no FFM API on JDK 8): their libraries' syscalls are not counted
    false_syms = set()
    hits = o + "/jna_hits.txt"
    if os.path.exists(hits):
        for l in open(hits, errors="replace").readlines()[2:]:
            f = [x.strip() for x in l.split("|")]
            if len(f) >= 4 and f[0] == "ffi":
                false_syms.add(f[3])
    java = names_in(f"{b}/syscalls_output_{t}/library_syscalls.txt")
    for sd in glob.glob(f"{b}/jna_ffi_analysis/syscalls/*/"):
        lib = os.path.basename(sd.rstrip("/"))
        starts = {l.strip() for l in open(f"{b}/jna_ffi_analysis/startfuncs/{lib}.txt") if l.strip()}
        if starts and starts <= false_syms:
            continue
        java |= names_in(sd + "syscalls.txt")
    # manual mappings are part of stage 7 (scripts/apply_manual_mappings.py): each library, supplied
    # ones included (LIBS_<t>/_supplied/), is analysed once from its full start list, so its
    # syscalls are already in library_syscalls.txt
    binary = names_in(f"{b}/syscalls_BIN_{t}/binary_syscalls.txt")
    for c in glob.glob(f"{d}/extra_components/*/syscalls.txt"):
        binary |= names_in(c)
    runc = names_in(RUNC) - java - binary
    unan = names_in(f"{b}/syscalls_unanalysed_{t}/unanalysed_syscalls.txt") - java - binary - runc
    rows = java | binary | runc | unan
    prof = {x for r in json.load(open(f"{b}/syscalls_output_{t}/{t}.json"))["syscalls"]
            if r.get("action") == "SCMP_ACT_ALLOW" for x in r["names"]}
    CHECK[t] = (sorted(prof - rows), sorted(rows - prof))

    s = glob.glob(f"{d}/Dynamic_Analysis/sysdig_outputs_*")[0]
    libs = {l.split()[4] for l in open(f"{s}/libs_loaded_raw.txt", errors="replace")
            if len(l.split()) > 4 and re.search(r"\.so(\.|$)", os.path.basename(l.split()[4]))}
    bins = {os.path.basename(l.strip()) for l in open(glob.glob(f"{s}/binaries_unique_*.txt")[0]) if l.strip()}
    jars = names_in(glob.glob(f"{s}/jars_unique_*.txt")[0])
    mapped_libs = len(glob.glob(f"{b}/syscalls_output_{t}/*/"))

    col = [None, total_n, resolved, *parts, platform, total_n - resolved - platform, *sw, None,
           len(java), len(binary), len(runc), len(unan), len(rows), None, col[23], col[24], col[25],
           len(rows & sw_all), len(rows - sw_all), len(sw_all - rows), None,
           len(libs), len(bins), len(jars), mapped_libs]
    V[t] = col

names = [c[0] + "-jdk8-buster" for c in COLS]
nc = len(COLS)
tex = ["% Generated by tools/make_tab_results_jdk8.py", "\\begin{table*}[t]", "\\centering",
       "\\caption{SysJava vs SWAT4J on the primary JDK 8 container images (Debian 10, Temurin 8u504).}",
       "\\label{tab:results}", "\\scriptsize", "\\setlength{\\tabcolsep}{3pt}",
       "\\begin{tabular}{@{}l" + "r" * nc + "@{}}", "\\toprule",
       " & " + " & ".join(c[2] for c in COLS) + " \\\\", " & " + " & ".join(c[3] for c in COLS) + " \\\\",
       " & " + " & ".join("JDK 8u504" for c in COLS) + " \\\\", " & " + " & ".join("Debian 10" for c in COLS) + " \\\\"]
md = ["| | " + " | ".join(f"{c[2]} {c[3]}<br>JDK 8u504<br>Debian 10" for c in COLS) + " |", "|---" * (nc + 1) + "|"]
for k, lab in enumerate(LABELS):
    if k in SECTIONS:
        tex.append(f"\\midrule\n\\multicolumn{{{nc+1}}}{{@{{}}l}}{{{lab}}} \\\\ \\midrule")
        md.append(f"| **{lab}** |" + " |" * nc); continue
    vals = [str(V[t][k]) for t in names]
    tex.append(("\\quad " if k in INDENT else "") + lab.strip() + " & " + " & ".join(vals) + " \\\\")
    plain = lab.strip().replace("\\_", "_").replace("\\$", "$").replace("$\\Delta$", "Δ").replace("$\\cup$", "∪").replace("$\\cap$", "∩")
    md.append(f"| {'↳ ' if k in INDENT else ''}{plain} | " + " | ".join(vals) + " |")
NOTE = ("Note: SysJava Resolved + Platform / Intrinsic + Not Found = JNI Total Natives; SWAT4J Resolved + Not Found = "
        "SWAT4J Natives Found: SWAT4J maps the native methods its own bytecode analysis (JTracer) finds, by name, "
        "with the third-party JNI libraries shipped in its repository (it never reads the Hadoop and RocksDB ones). "
        "Java Lib $\\cup$ Container Binary + Go Whitelist ($\\Delta$, runc entries not already counted) + Unmapped Lib "
        "($\\Delta$, syscalls of loaded libraries without a Java binding, not already counted) = Total Syscalls. "
        "Native methods are found on an RTA call graph (virtual and interface calls dispatched to the overrides of every "
        "class instantiated in reachable code). Natives in libraries the image does not ship are mapped to the released "
        "library (Solr: Hadoop 3.2.0 libhadoop, Hadoop 3.3.6 libhadoop for the 14 erasure-coding natives, netty epoll "
        "4.1.50, Lucene NativePosixUtil; OrientDB: jffi 1.3.11, NativePosixUtil; Elasticsearch: NativePosixUtil; "
        "Groovy: the jansi library bundled in jline 2.14.6; Tomcat: jsvc built from commons-daemon 1.2.4); each library is "
        "analysed once from all its mapped start functions. The remaining Not Found natives have no implementation in "
        "any library (e.g. jffi \\texttt{Foreign} natives never implemented upstream, JFR "
        "\\texttt{setCompressedIntegers} absent from the 8u504 libjvm). Container binaries are analysed from "
        "\\texttt{\\_start} and \\texttt{main}; runc is covered by the Go whitelist only. "
        "Storm: \\texttt{sync} in its generated profile comes only from FFM hits the detector inferred from Clojure "
        "class names (JDK 8 has no FFM API) and is not counted; Storm runs under the 172-syscall profile. "
        "Elasticsearch: SysPart cannot analyse the stripped ML \\texttt{controller}; its syscalls are recovered from "
        "the functions it imports. SWAT4J Java Lib = its static allowlist (JTracer); "
        "SWAT4J Dynamic = \\texttt{strace} of the container start-up. All ten containers run under their generated profiles.")
tex += ["\\bottomrule", "\\end{tabular}", "\\par\\smallskip", "\\begin{minipage}{\\textwidth}\\footnotesize", NOTE,
        "\\end{minipage}", "\\end{table*}"]
open(out + ".tex", "w").write("\n".join(tex) + "\n")
open(out + ".md", "w").write("\n".join(md) + "\n")
# ---- PDF (Computer Modern from matplotlib's BaKoMa TTFs; same style as tab:latest)
try:
    import matplotlib
except ImportError:
    sys.exit(f"wrote {out}.tex, {out}.md (no PDF: matplotlib not installed)")
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
FD = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data/fonts/ttf")
pdfmetrics.registerFont(TTFont("CMR", FD + "/cmr10.ttf")); pdfmetrics.registerFont(TTFont("DejaVu", FD + "/DejaVuSerif.ttf"))


def pdftext(s):
    for a, b in (("$\\Delta$", "\u0394"), ("$\\cup$", "\u222a"), ("$\\cap$", "\u2229")):
        s = s.replace(a, f"<font name='DejaVu'>{b}</font>")
    s = re.sub(r"\\texttt\{([^}]*)\}", r"\1", s).replace("\\$", "$")
    return s.replace("\\_", "<font name='DejaVu'>_</font>").replace("--", "<font name='DejaVu'>\u2013</font>")


cellst = ParagraphStyle("x", fontName="CMR", fontSize=8, leading=9.5)
prow = [[""] + [c[2] for c in COLS], [""] + [c[3] for c in COLS], [""] + ["JDK 8u504"] * nc, [""] + ["Debian 10"] * nc]
sec = []
for k, lab in enumerate(LABELS):
    if k in SECTIONS:
        prow.append([lab] + [""] * nc); sec.append(len(prow) - 1); continue
    prow.append([Paragraph(("&nbsp;&nbsp;&nbsp;" if k in INDENT else "") + pdftext(lab.strip()), cellst)] + [str(V[t][k]) for t in names])
tbl = Table(prow, colWidths=[150] + [62] * nc)
st = [("FONT", (0, 0), (-1, -1), "CMR", 8), ("ALIGN", (1, 0), (-1, 3), "CENTER"), ("ALIGN", (1, 4), (-1, -1), "RIGHT"),
      ("LINEABOVE", (0, 0), (-1, 0), 0.9, colors.black), ("LINEBELOW", (0, -1), (-1, -1), 0.9, colors.black),
      ("TOPPADDING", (0, 0), (-1, -1), 0.8), ("BOTTOMPADDING", (0, 0), (-1, -1), 0.8)]
for i in sec:
    st += [("SPAN", (0, i), (-1, i)), ("LINEBELOW", (0, i), (-1, i), 0.4, colors.black), ("LINEABOVE", (0, i), (-1, i), 0.4, colors.black)]
tbl.setStyle(TableStyle(st))
doc = SimpleDocTemplate(out + ".pdf", pagesize=landscape(A4), leftMargin=30, rightMargin=30, topMargin=30, bottomMargin=30)
doc.build([Paragraph("Table II: SysJava vs SWAT4J on the primary JDK 8 container images (Debian 10, Temurin 8u504).",
                     ParagraphStyle("c", fontName="CMR", fontSize=11, leading=14)), Spacer(1, 6), tbl, Spacer(1, 4),
           Paragraph(pdftext(NOTE), ParagraphStyle("n", fontName="CMR", fontSize=8.5, leading=11))])
print("wrote", out + ".tex", out + ".md", out + ".pdf")
print("profile vs rows (only in profile, only in rows):", CHECK)
