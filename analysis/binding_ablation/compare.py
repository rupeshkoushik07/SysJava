#!/usr/bin/env python3
"""Summarise an ablation run produced by run_ablation.sh in one table:

  SysJava (binding)     mapped libraries start from the functions the app's
                        native methods were mapped to (variant M, else B);
                        loaded libraries with nothing mapped start from every
                        function (variant U)
  SysJava (no binding)  every library starts from every function (A, U)

The executables, runtime set and fallbacks are identical across variants, so
each variant's full policy is the archived final policy with the library set
swapped in: policy(V) = (archived policy - archived library set) | V's library set.

Usage: compare.py <img> [archived-results-dir]
  MAPPING_DIR=<outputs_<img>>  SYSDIG_DIR=<sysdig_outputs_<img>>  read the
  bytecode reports and the sysdig trace from a pipeline workspace, for runs
  whose Final_results are not assembled yet
"""
import os
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
img = sys.argv[1]
results = Path(sys.argv[2]) if len(sys.argv) > 2 else \
    Path.home() / "Prototype/Final_results_echotrace" / img
arch = results / "Binary_Analysis" / f"syscalls_output_{img}"
mapping = Path(os.environ.get("MAPPING_DIR", results / "Bytecode_Analysis" / f"outputs_{img}"))
sysdig = Path(os.environ.get("SYSDIG_DIR",
                             results / "Dynamic_Analysis" / f"sysdig_outputs_{img}"))
run = HERE / img


def read_set(path):
    """Lines of a file as a set; None if it is missing or empty (a run that is
    still going or was killed leaves an empty syscalls.txt)."""
    try:
        return {l.strip() for l in path.read_text().splitlines() if l.strip()} or None
    except FileNotFoundError:
        return None


def size(s):
    return "running" if s is None else f"{len(s):,}"


def names(s):
    return ", ".join(f"`{x}`" for x in sorted(s)) if s else "none"


def union(sets):
    sets = list(sets)
    return None if any(s is None for s in sets) else set().union(*sets)


def note(path):
    """A one-line note file's text; None if there is none."""
    return path.read_text().strip() if path.exists() else None


# ------------------------------------------------------------ native methods
native_methods = len(read_set(mapping / "native_methods.txt") or ())
bound = []               # (library, native method, mechanism) per mapping line
unmapped = Counter()     # reason -> native methods
MECHANISM = {"JNI": "JNI symbol naming", "JNI_DYNAMIC": "dynamic JNI registration",
             "REGISTERED": "RegisterNatives tables", "JVM": "JVM native-method tables",
             "JVM_BUILTIN": "JVM native-method tables", "NETTY": "Netty native naming",
             "DIRECT_LIBC_BRIDGE": "direct libc bridges", "SIGAR_LIST_BRIDGE": "SIGAR bridges"}
for line in (mapping / "mapped_method_syscalls.txt").read_text().splitlines():
    m = re.match(r"^(\S+?):(\S+) -> (\S+) \[([^\]]+)\]$", line)
    if m and m.group(1).startswith("LIBS_") and "?" not in m.group(4):
        bound.append((m.group(1).rsplit("/", 1)[-1], m.group(2),
                      MECHANISM.get(m.group(4), m.group(4))))
    elif "[INTRINSIC]" in line:
        unmapped["intrinsic"] += 1
    elif "PLATFORM_EXCLUDED" in line:
        unmapped["windows"] += 1
    elif "NOT_FOUND_IN_LIBS" in line:
        unmapped["not_found"] += 1
    elif line.strip():
        unmapped["unresolved"] += 1
# Why a native method stays unmapped, for "N <verb phrase>" (plural, singular).
WHY_UNMAPPED = {"intrinsic": ("are handled inside the JVM (intrinsics)",
                              "is handled inside the JVM (an intrinsic)"),
                "windows": ("are Windows-only", "is Windows-only"),
                "not_found": ("have no matching function in any library",
                              "has no matching function in any library"),
                "unresolved": ("could not be resolved", "could not be resolved")}
CLASSIC_JNI = {"JNI symbol naming", "dynamic JNI registration", "RegisterNatives tables",
               "JVM native-method tables"}

# FFM downcalls (ffi_hits.txt: caller | library | symbol | mechanism | jar);
# upcall stubs name no library ("<?>").
ffm_found, ffm_jars = set(), set()
if (mapping / "ffi_hits.txt").exists():
    for line in (mapping / "ffi_hits.txt").read_text().splitlines():
        p = line.split(" | ")
        if len(p) >= 5 and p[3] == "downcallHandle" and p[1] != "<?>":
            ffm_found.add(p[2])
            ffm_jars.add(p[4].strip())
# Bindings through the other foreign-function libraries SysJava detects, per
# library; None when this run's outputs predate those detectors.
OTHER_FFI = {"JNA": ("jna_directmap_hits.txt", "jna_dyn_hits.txt", "jna_iface_hits.txt"),
             "JNR-FFI": ("jnr_ffi_hits.txt",)}
other_ffi = None
if all((mapping / f).exists() for files in OTHER_FFI.values() for f in files):
    other_ffi = {k: sum(1 for f in files for l in (mapping / f).read_text().splitlines()
                        if " | " in l and not l.startswith("Format:"))
                 for k, files in OTHER_FFI.items()}

# ------------------------------------------------------- mapped libraries
# The libraries this ablation analysed (one binding start list each). A
# library can appear under two names (a SONAME link and its file); counting
# only these keeps a native method from being counted once per name.
libs = sorted(p.name[:-len(".txt")] for p in (run / "starts/B").glob("*.txt"))
mapped = {}              # library -> native methods mapped into it
how = {}                 # native method -> resolution mechanism
for lib, method, mech in bound:
    if lib in libs:
        mapped.setdefault(lib, set()).add(method)
        how.setdefault(method, mech)
how = Counter(how.values())
methods = set().union(*mapped.values()) if mapped else set()
# FFM-bound libraries: no native method maps into them; their binding start
# list is the downcall symbols they define.
ffm = {l: (read_set(run / "starts/B" / f"{l}.txt") or set()) & ffm_found
       for l in libs if l not in mapped}
ffm = {l: s for l, s in ffm.items() if s}
ffm_mapped = set().union(*ffm.values()) if ffm else set()
what = "native methods and FFM downcalls" if ffm else "native methods"
# Binding results taken from the SysJava pipeline's own run (B/<lib>/SOURCE).
from_pipeline = [l for l in libs if (run / "B" / l / "SOURCE").exists()]
rows = {}
for lib in libs:
    r = rows[lib] = {
        "mapped": len(mapped.get(lib, ())),
        "starts_B": len(read_set(run / "starts/B" / f"{lib}.txt") or ()),
        "starts_A": len(read_set(run / "starts/A" / f"{lib}.txt") or ()),
        "B_arch": read_set(arch / lib / "syscalls.txt"),
        "B": read_set(run / "B" / lib / "syscalls.txt"),
        "A": read_set(run / "A" / lib / "syscalls.txt"),
        "dnf": note(run / "A" / lib / "DID_NOT_FINISH"),   # why the A run never finished
        "starts_M": len(read_set(run / "starts/M" / f"{lib}.txt") or ()),
        "M": read_set(run / "M" / lib / "syscalls.txt"),
    }
    # Binding column: every mapped function (M) where that run exists,
    # otherwise the archived start list (B).
    r["bind"], r["starts_bind"] = (r["M"], r["starts_M"]) if r["M"] is not None \
        else (r["B"], r["starts_B"])

# ------------------------------------- loaded libraries with nothing mapped
# loaded_libraries.txt: every .so the running app had mapped (/proc/<pid>/maps);
# loaded_unmapped.txt: the analysed copies of those SysJava mapped nothing to,
# run from every function as variant U.
loaded = {Path(p).name for p in read_set(run / "loaded_libraries.txt") or ()}
u_libs = sorted(Path(p).name for p in read_set(run / "loaded_unmapped.txt") or ())
u = {l: read_set(run / "U" / l / "syscalls.txt") for l in u_libs}
u_funcs = {l: len(read_set(run / "U" / l / "startfuncs_with_addr.txt") or ()) for l in u_libs}
# Native libraries the java process loaded in SysJava's sysdig trace
# (raw_capture.txt lines: time event pid comm path flags); this is the
# "Libraries Observed" count. Other processes (ls, grep, ...) are left out.
traced = set()
capture = sysdig / "raw_capture.txt"
if capture.exists():
    for line in capture.read_text().splitlines():
        p = line.split()
        if len(p) >= 5 and p[3] == "java" and re.search(r"\.so(\.\d+)*$", Path(p[4]).name):
            traced.add(Path(p[4]).name)

policy_arch = read_set(arch / f"{img}.txt")
lib_arch = union(rows[l]["B_arch"] for l in libs)
# Everything in the final policy that is not from these libraries; unknown
# until the pipeline has assembled its policy.
rest = policy_arch - lib_arch if policy_arch and lib_arch is not None else None
uB = union(rows[l]["B"] for l in libs)
# A library whose no-binding syscalls could not be resolved (its run did not
# finish; A/<lib>/DID_NOT_FINISH says why) keeps its row, marked "not
# resolved", but stays out of the totals, so both columns cover the same
# libraries; the reason is given below the table.
dnf = [l for l in libs if rows[l]["A"] is None and rows[l]["dnf"]]
shown = [l for l in libs if l not in dnf]
uBind = union(rows[l]["bind"] for l in shown)
uA = union(rows[l]["A"] for l in shown)


def policy(s):
    return "running" if s is None or rest is None else f"{len(rest | s):,}"


def and_list(items):
    items = list(items)
    return ", ".join(items[:-1]) + " and " + items[-1] if len(items) > 1 else "".join(items)


# ------------------------------------------------------------- the table
# One row per mapped library: binding starts from the functions its native
# methods (or FFM downcalls) are mapped to, no binding from every function.
env = run / "environment.md"   # "- Key: value" lines: container, versions, setup
facts = {}
if env.exists():
    for line in env.read_text().splitlines():
        m = re.match(r"^- ([^:]+): (.+)$", line)
        if m:
            facts[m.group(1)] = m.group(2)
app = facts.get("Application", "The application")
out = [f"# SysJava with and without binding recovery: {img}", ""]
# The container and its versions, right above the table.
out += [f"- **{k}:** {facts[k]}"
        for k in ("Container", "Application", "Distro", "JDK", "Native libraries") if k in facts]
# An Interface column only when the bindings use more than JNI.
iface = (lambda l: "FFM" if l in ffm else "JNI") if ffm else None
out += ["",
        "| Library " + ("| Interface " if iface else "") + "| Binding: start functions "
        "| Binding: syscalls | No binding: start functions | No binding: syscalls |",
        "|---|" + ("---|" if iface else "") + "---:|---:|---:|---:|"]
# JNI libraries first, then FFM ones.
for lib in sorted(libs, key=lambda l: (iface(l) != "JNI", l)) if iface else libs:
    r = rows[lib]
    out.append(f"| {lib} " + (f"| {iface(lib)} " if iface else "")
               + f"| {r['starts_bind']:,} | {size(r['bind'])} "
               f"| {r['starts_A']:,} | {'not resolved' if lib in dnf else size(r['A'])} |")
out.append((f"| **All except {and_list(dnf)}** " if dnf else f"| **All {len(shown)} libraries** ")
           + ("| " if iface else "")
           + f"| **{sum(rows[l]['starts_bind'] for l in shown):,}** | **{size(uBind)}** "
           f"| **{sum(rows[l]['starts_A'] for l in shown):,}** | **{size(uA)}** |")

# ------------------------------------------------------- what the table means
# What SysJava found and mapped, per library: native methods (JNI) and FFM
# downcalls are counted separately.
jni = (f"SysJava's bytecode analysis found {native_methods:,} native methods (Java methods "
       f"declared `native`, in the application and the JDK) and mapped {len(methods):,} of "
       "them to C functions: "
       + and_list(f"{len(mapped[l])} in {l}" for l in sorted(mapped, key=lambda l: (-len(mapped[l]), l)))
       + " (" + ", ".join(f"{n} through {mech}" for mech, n in how.most_common()) + ").")
if sum(unmapped.values()) == native_methods - len(methods) and unmapped:
    jni += (f" Of the other {native_methods - len(methods)}, "
            + and_list(f"{n} {WHY_UNMAPPED[why][n == 1]}" for why, n in unmapped.most_common())
            + ".")
if not ffm and set(how) <= CLASSIC_JNI:
    jdk = facts.get("JDK", "").split(" (")[0]
    jni += (f" {app} is an older application" + (f" on {jdk}" if jdk else "")
            + " and binds native code only through classic JNI.")
out += ["", "**Native methods (JNI).** " + jni, ""]
if ffm:
    missing = sorted(ffm_found - ffm_mapped)
    out += ["**FFM downcalls.** " + app + " also calls native functions directly through the "
            "Foreign Function & Memory (FFM) API" + (" in " + and_list(sorted(ffm_jars)) if ffm_jars else "")
            + f". SysJava found downcall handles for {len(ffm_found)} native functions, separate "
            f"from the {native_methods:,} native methods, and mapped {len(ffm_mapped)} of them to "
            "the libraries that define them: "
            + and_list(f"{len(ffm[l])} in {l}" for l in sorted(ffm, key=lambda l: -len(ffm[l])))
            + "." + (f" The other {len(missing)} (e.g. "
                     + ", ".join(f"`{s}`" for s in missing[:2])
                     + ") are not exported by these libraries." if missing else ""), ""]
if other_ffi is not None:
    out[-2] += (" SysJava found no " + " or ".join(sorted(other_ffi)) + " bindings."
                if all(n == 0 for n in other_ffi.values()) else
                " SysJava also found " + and_list(f"{n} {k} bindings" for k, n in
                                                   sorted(other_ffi.items()) if n) + ".")
# Which libraries the trace saw, and how the mapped ones relate to them.
where = ""
if traced:
    seen = [l for l in libs if l in traced]
    unseen = [l for l in libs if l not in traced]
    where = (f"All {len(libs)} libraries are among the {len(traced)} native libraries the JVM "
             "loaded at runtime (sysdig trace)" if not unseen else
             f"At runtime the JVM loaded {len(traced)} native libraries (sysdig trace). The "
             f"mapped functions fall in {len(libs)} libraries: {len(seen)} of those")
    if unseen:
        parts = []
        if [l for l in unseen if l in loaded]:
            parts.append(", ".join(l for l in unseen if l in loaded)
                         + ", which is loaded but missing from the trace")
        if [l for l in unseen if loaded and l not in loaded]:
            parts.append(", ".join(l for l in unseen if l not in loaded)
                         + ", which is not loaded at all")
        where += ", plus " + (", and ".join(parts) if parts else ", ".join(unseen))
    where += ". "

counted = (where + "For each library, SysPart builds a call graph and collects every syscall "
           f"reachable from the start functions: with binding, the functions the {what} map to; without "
           "binding, every function in the library, since without the mapping any of them could "
           "be called. Both use the same library files and SysPart build. The last row adds up "
           "the start functions and counts each syscall once.")
if from_pipeline:
    counted += (" For " + and_list(from_pipeline) + ", the binding numbers come from the SysJava "
                "pipeline's own run (same start functions; where both were computed, they agree).")
out += ["**How the syscalls were counted.** " + counted, ""]

if uBind is not None and uA is not None and all(rows[l]["A"] and rows[l]["bind"] for l in shown):
    extra = {l: rows[l]["A"] - rows[l]["bind"] for l in shown}
    top = [l for l in sorted(shown, key=lambda l: -len(extra[l])) if extra[l]][:3]
    gap = sorted(uA - uBind)
    out += [f"**Result.** Across the {len(shown)} libraries"
            + (" with both results" if dnf else "") + ", starting from the mapped functions "
            f"reaches {len(uBind)} syscalls; starting from every function reaches {len(uA)}. "
            + ("Per library, the gap is largest in "
               + and_list(f"{l} (+{len(extra[l])})" for l in top)
               + ". " if top else "")
            + f"Reached only without binding ({len(gap)}): "
            + (and_list(f"`{s}`" for s in gap) if gap else "none") + ".", ""]

for l in dnf:
    r = rows[l]
    covered = uBind is not None and r["bind"] is not None and r["bind"] <= uBind
    out += [f"**Why {l} is not resolved without binding.** With binding, SysPart starts from "
            f"its {r['starts_bind']:,} mapped functions and resolves {size(r['bind'])} syscalls. "
            f"Without binding, it has to start from all {r['starts_A']:,}, and {r['dnf']}. "
            f"The last row leaves {l} out"
            + ("; with binding it adds no syscall the other libraries do not already reach"
               if covered else "") + ".", ""]

# ------------------------------------------------- syscall names per library
out += ["## Syscalls per library", ""]
for lib in libs:
    r = rows[lib]
    out.append(f"### {lib}")
    out.append(f"- Binding ({size(r['bind'])}): "
               + ("running" if r["bind"] is None else names(r["bind"])))
    if r["A"] is not None and r["bind"] is not None:
        out.append(f"- Only without binding (+{len(r['A'] - r['bind'])}): "
                   + names(r["A"] - r["bind"]))
    elif lib in dnf:
        out.append(f"- No binding: not resolved: {r['dnf']}")
    out.append("")

# ------------------------------------------- syscall x library matrix (TSV)
# B = reached with binding, A = reached only without binding.
every = set().union(*(s for r in rows.values() for s in (r["bind"], r["A"]) if s))
matrix = ["\t".join(["syscall"] + libs + ["policy_binding", "policy_no_binding"])]
for sc in sorted(every):
    cells = ["B" if r["bind"] and sc in r["bind"] else "A" if r["A"] and sc in r["A"] else ""
             for r in (rows[l] for l in libs)]
    cells += ["yes" if s is not None and rest is not None and sc in rest | s else ""
              for s in (uBind, uA)]
    matrix.append("\t".join([sc] + cells))
(run / "per_library_syscalls.tsv").write_text("\n".join(matrix) + "\n")

text = "\n".join(out) + "\n"
(run / "summary.md").write_text(text)
print(text)

# ------------------------------- loaded libraries with nothing mapped (U)
# Kept apart from the binding comparison: every function of each loaded
# library SysJava mapped nothing to, against the binding policy above.
if u_libs and uBind is not None and rest is not None:
    base = rest | uBind
    uU = union(u.values())
    lines = [f"# Loaded libraries with no mapped native methods: {img}", "",
             f"The app had {len(loaded)} libraries loaded (`loaded_libraries.txt`); "
             f"{len(u_libs)} of them have no native method mapped to them. Each is analysed "
             f"here from every function. Container policy with binding: {policy(uBind)}.", "",
             "| Library | Start functions (every function) | Syscalls | New to the policy |",
             "|---|---:|---:|---:|"]
    for l in u_libs:
        if u[l] is None:
            lines.append(f"| {l} | {u_funcs[l] or '–'} | running | – |")
        else:
            lines.append(f"| {l} | {u_funcs[l]:,} | {len(u[l])} | {len(u[l] - base)} |")
    if uU is not None:
        lines += [f"| **Container policy with these added** | | | **{policy(uBind | uU)}** |",
                  "", f"Syscalls they add ({len((rest | uU) - base)}): "
                  + names((rest | uU) - base) + ".", ""]
    lines += ["## Syscalls per library", ""]
    for l in u_libs:
        lines += [f"### {l}", f"- Every function ({size(u[l])}): "
                  + ("running" if u[l] is None else names(u[l])), ""]
    (run / "unmapped_loaded.md").write_text("\n".join(lines) + "\n")
