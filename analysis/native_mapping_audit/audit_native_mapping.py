#!/usr/bin/env python3
"""
RQ1 audit: per-declaration reconciliation of SysJava (EchoTrace mapper,
mapped_updated.py) and SWAT4J (swat4j_mapping.py) native-method mappings.

For every app it reads, from the SAME denominator file (native_methods.txt):
  - EchoTrace:  mapped_method_syscalls.txt   (one line per declaration, tagged)
  - SWAT4J:     swat4j_mapped_methods.txt / swat4j_intrinsic_methods.txt /
                swat4j_unmapped_methods.txt

and writes (into --out):
  per_app_summary.csv        denominator + per-category counts for both tools
  per_method.csv             one row per (app, declaration) with both verdicts
                             and the automatic evidence checks
  auto_check_failures.csv    every mapping that fails an automatic check
  validation_sample.csv      seeded stratified sample of SysJava-only
                             ("additional") mappings for manual review

Usage:
  ./run_audit.sh            (see that script for the exact app list)
"""
import argparse
import collections
import csv
import functools
import os
import random
import re
import subprocess

# EchoTrace tag -> (reporting category, evidence source)
ET_CATEGORY = {
    "JNI":                   ("jni_static",      "nm: exported Java_* symbol"),
    "JNI_DYNAMIC":           ("registered",      "binary: third-party RegisterNatives table"),
    "REGISTERED":            ("registered",      "binary: libjvm/lib RegisterNatives table"),
    "JVM":                   ("registered",      "binary: libjvm RegisterNatives table (JVM_*)"),
    "NETTY":                 ("netty_name",      "nm: netty_* symbol name pattern"),
    "JVM_BUILTIN":           ("manual_rule",     "hand-written table JVM_BUILTIN_NATIVES"),
    "DIRECT_LIBC_BRIDGE":    ("manual_rule",     "hand-written libc bridge table"),
    "SIGAR_LIST_BRIDGE":     ("manual_rule",     "hand-written SIGAR_LIST_BRIDGES table"),
    "INTRINSIC":             ("intrinsic",       "curated intrinsic whitelist"),
    "PLATFORM_EXCLUDED":     ("platform",        "keyword list (win32/kqueue/Darwin/...)"),
    "REGISTERED? UNRESOLVED": ("not_found",      "table entry, symbol not located"),
    "NOT_FOUND_IN_LIBS":     ("not_found",       "-"),
}
# Manual-validation sample size per stratum of SysJava-only results. RegisterNatives
# recovery is the paper's main claim, so it gets the largest share; small strata
# are reviewed exhaustively.
STRATUM_SIZE = {"registered": 60, "jni_partial": 25, "netty_name": 20, "platform": 20,
                "manual_rule": 30, "jni_static": 20, "intrinsic": 20}

MAPPED_CATS = {"jni_static", "registered", "netty_name", "manual_rule"}
CLASSIFIED_CATS = {"intrinsic", "platform"}

LINE_MAPPED = re.compile(r"^(?:(?P<lib>[^:]+\.so[^:]*):)?(?P<m>\S+?) -> (?P<sym>\S+) \[(?P<tag>[^\]]+)\](?P<rest>.*)$")
LINE_TAGONLY = re.compile(r"^(?P<m>\S+) \[(?P<tag>[^\]]+)\]$")
LINE_COLON = re.compile(r"^(?P<m>\S+): (?P<tag>NOT_FOUND_IN_LIBS|PLATFORM_EXCLUDED)(?: \((?P<why>.*)\))?$")
ALIAS = re.compile(r"\(alias of (\S+)\)")
SWAT_LINE = re.compile(r"^(?P<m>\S+) -> (?P<sym>\S+) @ (?P<lib>\S+) \[(?P<strat>[^\]]+)\]$")


# ---------------------------------------------------------------- JNI naming

def jni_mangle(s):
    out = []
    for ch in s:
        if ch.isalnum() and ord(ch) < 128:
            out.append(ch)
        elif ch == "_":
            out.append("_1")
        elif ch == ".":
            out.append("_")
        else:
            out.append("_0%04x" % ord(ch))
    return "".join(out)


def expected_jni_symbol(method):
    cls, _, name = method.rpartition(".")
    return "Java_" + jni_mangle(cls) + "_" + jni_mangle(name)


def jni_name_matches(method, sym):
    exp = expected_jni_symbol(method)
    return sym == exp or sym.startswith(exp + "__")


def netty_name_matches(method, sym):
    """netty_<area>_<classtoken>_<method>: method name must match exactly and
    the class token must equal the Java simple class name (case-insensitive)."""
    cls, _, name = method.rpartition(".")
    simple = cls.rsplit(".", 1)[-1].split("$")[-1]
    # Netty registers XStaticallyReferencedJniMethods under the C module "x".
    simple = simple.replace("StaticallyReferencedJniMethods", "") or simple
    if not sym.endswith("_" + name):
        return False
    head = sym[: -(len(name) + 1)]
    return head.lower().endswith("_" + simple.lower())


# ------------------------------------------------------------- ELF symbols

@functools.lru_cache(maxsize=None)
def defined_symbols(path):
    syms = set()
    for args in (["nm", "-D", "--defined-only", path], ["nm", "--defined-only", path]):
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=120)
        except Exception:
            continue
        for line in r.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 3:
                syms.add(parts[2].split("@")[0])
    return frozenset(syms)


def resolve_lib(app_dir, app, raw):
    """Map the library string printed by either tool to a file on disk."""
    if not raw:
        return None
    if os.path.isabs(raw) and os.path.isfile(raw):
        return raw
    libs_root = os.path.join(app_dir, "Dataset", "LIBS_" + app)
    m = re.search(r"LIBS_[^/]+/(.*)$", raw)
    if m:
        cand = os.path.join(libs_root, m.group(1))
        if os.path.isfile(cand):
            return cand
    base = os.path.basename(raw)
    for root, _, files in os.walk(libs_root):
        if base in files:
            return os.path.join(root, base)
    return None


# ------------------------------------------------------------------ parsing

def read_lines(path):
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8", errors="replace") as f:
        return [l.rstrip("\n") for l in f if l.strip()]


def parse_echotrace(path):
    recs = {}
    for line in read_lines(path):
        m = LINE_MAPPED.match(line)
        if m:
            tag = m.group("tag")
            alias = ALIAS.search(m.group("rest") or "")
            recs.setdefault(m.group("m"), dict(tag=tag, lib=m.group("lib") or "",
                                               sym=m.group("sym"),
                                               alias=alias.group(1) if alias else ""))
            continue
        m = LINE_TAGONLY.match(line)
        if m:
            recs.setdefault(m.group("m"), dict(tag=m.group("tag"), lib="", sym="", alias=""))
            continue
        m = LINE_COLON.match(line)
        if m:
            recs.setdefault(m.group("m"), dict(tag=m.group("tag"), lib="", sym=m.group("why") or "", alias=""))
            continue
        recs.setdefault("__unparsed__", []).append(line)
    return recs


def parse_swat(out_dir):
    recs = {}
    for line in read_lines(os.path.join(out_dir, "swat4j_mapped_methods.txt")):
        m = SWAT_LINE.match(line)
        if m:
            recs[m.group("m")] = dict(strategy=m.group("strat"), sym=m.group("sym"), lib=m.group("lib"))
    for m in read_lines(os.path.join(out_dir, "swat4j_intrinsic_methods.txt")):
        recs.setdefault(m.strip(), dict(strategy="INTRINSIC", sym="", lib=""))
    return recs


def load_table(path, sep="|"):
    """jvm_dynamic_mapping.txt / jni_dynamic_bindings.txt -> {(method, sym)}."""
    rows = set()
    for line in read_lines(path):
        if line.startswith("#"):
            continue
        parts = line.split(sep)
        if len(parts) >= 4:
            rows.add((parts[1], parts[3]))
    return rows


# ------------------------------------------------------------------- checks

def check_echotrace(app_dir, app, method, r, tables):
    """Return (symbol_in_lib, name_or_table_ok, note)."""
    tag = r["tag"]
    if tag not in ("JNI", "JNI_DYNAMIC", "REGISTERED", "JVM", "NETTY",
                   "JVM_BUILTIN", "DIRECT_LIBC_BRIDGE", "SIGAR_LIST_BRIDGE"):
        return "", "", ""
    lib = resolve_lib(app_dir, app, r["lib"])
    in_lib = "n/a"
    if lib:
        in_lib = "yes" if r["sym"] in defined_symbols(lib) else "no"
    target = r["alias"] or method
    note = ""
    if tag == "JNI":
        ok = jni_name_matches(target, r["sym"])
        if not ok and r["alias"] == "":
            note = "Java_ symbol does not encode this Java method"
    elif tag in ("REGISTERED", "JVM", "JNI_DYNAMIC"):
        # Shaded Netty (e.g. org.apache.storm.shade.io.netty.*) registers the
        # same C functions; the recovered table lists the unshaded class names.
        unshaded = re.sub(r"^.+?\.io\.netty\.", "io.netty.", target)
        ok = any((k, r["sym"]) in tables for k in (method, target, unshaded))
        if not ok:
            note = "pair not present in recovered RegisterNatives table"
    elif tag == "NETTY":
        ok = netty_name_matches(target, r["sym"])
        if not ok:
            note = "netty symbol class/method token mismatch"
    else:
        ok = None
        note = "manual rule; needs manual review"
    return in_lib, ("" if ok is None else ("yes" if ok else "no")), note


def check_swat(app_dir, app, method, r):
    s = r["strategy"]
    if s == "INTRINSIC":
        return "", "", ""
    sym = r["sym"] if r["sym"].startswith(("Java_", "JVM_", "netty")) else "Java_" + r["sym"]
    lib = resolve_lib(app_dir, app, r["lib"]) if "/Dataset/" in r["lib"] or "LIBS_" in r["lib"] else (r["lib"] if os.path.isfile(r["lib"]) else None)
    in_lib = "n/a" if not lib else ("yes" if sym in defined_symbols(lib) else "no")
    note = ""
    if s == "Java_XXX":
        ok = jni_name_matches(method, sym)
        if not ok:
            note = "dotted-name collision: Java_ symbol is for a different method"
    elif s == "NETTY_HEURISTIC":
        ok = netty_name_matches(method, sym)
        if not ok:
            note = "suffix heuristic picked a symbol for another class/method"
    elif s == "JVM_XXX":
        ok = None
        note = "from OpenJDK source table (host JDK)"
    else:
        ok = None
    host = "host-JDK" if r["lib"].startswith("/usr/") else ""
    return in_lib, ("" if ok is None else ("yes" if ok else "no")), (note + (" [" + host + "]" if host else "")).strip()


# --------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", nargs="+", required=True,
                    help="label=app_dir pairs; app_dir holds Dataset/ and Bytecode_Analysis/outputs_<dirname>/")
    ap.add_argument("--swat-override", nargs="*", default=[],
                    help="label=dir pairs whose SWAT4J outputs live elsewhere")
    ap.add_argument("--out", required=True)
    ap.add_argument("--per-stratum", type=int, default=12)
    ap.add_argument("--seed", type=int, default=20261104)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    overrides = dict(kv.split("=", 1) for kv in args.swat_override)

    per_method_rows, summary_rows, unparsed = [], [], []
    for spec in args.app:
        label, app_dir = spec.split("=", 1)
        app_dir = os.path.abspath(os.path.expanduser(app_dir))
        app = os.path.basename(app_dir.rstrip("/"))
        bdir = os.path.join(app_dir, "Bytecode_Analysis", "outputs_" + app)
        methods = list(dict.fromkeys(m.strip() for m in read_lines(os.path.join(bdir, "native_methods.txt"))))
        et = parse_echotrace(os.path.join(bdir, "mapped_method_syscalls.txt"))
        unparsed += [(label, l) for l in et.pop("__unparsed__", [])]
        swat = parse_swat(overrides.get(label, bdir))
        tables = load_table(os.path.join(bdir, "jvm_dynamic_mapping.txt")) | \
            load_table(os.path.join(bdir, "jni_dynamic_bindings.txt"))

        cnt = collections.Counter()
        for m in methods:
            r = et.get(m)
            tag = r["tag"] if r else "MISSING_FROM_OUTPUT"
            cat = ET_CATEGORY.get(tag, ("not_found", ""))[0] if r else "missing"
            if tag == "JNI" and r and re.search(r"_1|_0[0-9a-f]{4}|__", r["sym"][5:]):
                cat_detail = "jni_partial"
            else:
                cat_detail = cat
            s = swat.get(m)
            s_strat = s["strategy"] if s else "UNMAPPED"
            s_cat = {"Java_XXX": "jni_static", "JVM_XXX": "jvm_source",
                     "NETTY_HEURISTIC": "netty_heuristic", "INTRINSIC": "intrinsic"}.get(s_strat, "mapped_other" if s else "not_found")

            et_in, et_ok, et_note = check_echotrace(app_dir, app, m, r, tables) if r else ("", "", "")
            sw_in, sw_ok, sw_note = check_swat(app_dir, app, m, s) if s else ("", "", "")

            et_acc = cat in MAPPED_CATS | CLASSIFIED_CATS
            sw_mapped = s_cat in ("jni_static", "jvm_source", "netty_heuristic", "mapped_other")
            same_sym = ""
            if r and s and r["sym"] and s["sym"]:
                ssym = s["sym"] if s["sym"].startswith(("Java_", "JVM_", "netty")) else "Java_" + s["sym"]
                same_sym = "yes" if ssym == r["sym"] else "no"

            cnt["denominator"] += 1
            cnt["et_" + cat_detail] += 1
            cnt["sw_" + s_cat] += 1
            cnt["et_mapped"] += cat in MAPPED_CATS
            cnt["et_accounted"] += et_acc
            cnt["sw_mapped"] += sw_mapped
            cnt["sw_accounted"] += sw_mapped or s_cat == "intrinsic"
            cnt["both_mapped"] += (cat in MAPPED_CATS) and sw_mapped
            cnt["et_only_mapped"] += (cat in MAPPED_CATS) and not sw_mapped
            cnt["sw_only_mapped"] += sw_mapped and cat not in MAPPED_CATS
            cnt["both_mapped_symbol_differs"] += same_sym == "no"
            cnt["et_auto_fail"] += et_ok == "no" or et_in == "no"
            cnt["sw_auto_fail"] += sw_ok == "no" or sw_in == "no"

            per_method_rows.append(dict(
                app=label, method=m, et_tag=tag, et_category=cat_detail,
                et_symbol=r["sym"] if r else "", et_lib=os.path.basename(r["lib"]) if r else "",
                et_alias=r["alias"] if r else "", et_symbol_in_lib=et_in, et_name_or_table_ok=et_ok,
                et_note=et_note, swat_strategy=s_strat, swat_symbol=s["sym"] if s else "",
                swat_lib=s["lib"] if s else "", swat_symbol_in_lib=sw_in, swat_name_ok=sw_ok,
                swat_note=sw_note, same_symbol=same_sym,
                additional=("yes" if et_acc and not (sw_mapped or s_cat == "intrinsic") else "no"),
            ))
        summary_rows.append(dict(app=label, source_dir=app_dir, **cnt))

    def write(name, rows, fields=None):
        fields = fields or list(rows[0].keys())
        with open(os.path.join(args.out, name), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore", restval=0)
            w.writeheader()
            w.writerows(rows)

    sfields = ["app", "source_dir", "denominator", "et_accounted", "et_mapped",
               "et_jni_static", "et_jni_partial", "et_registered", "et_netty_name", "et_manual_rule",
               "et_intrinsic", "et_platform", "et_not_found", "et_missing",
               "sw_accounted", "sw_mapped", "sw_jni_static", "sw_jvm_source", "sw_netty_heuristic",
               "sw_intrinsic", "sw_not_found",
               "both_mapped", "et_only_mapped", "sw_only_mapped", "both_mapped_symbol_differs",
               "et_auto_fail", "sw_auto_fail"]
    write("per_app_summary.csv", summary_rows, sfields)
    write("per_method.csv", per_method_rows)
    fails = [r for r in per_method_rows
             if "no" in (r["et_symbol_in_lib"], r["et_name_or_table_ok"], r["swat_symbol_in_lib"], r["swat_name_ok"])]
    write("auto_check_failures.csv", fails or [dict(app="")], list(per_method_rows[0].keys()))

    # Stratified sample of additional SysJava results: stratum = et_category.
    rng = random.Random(args.seed)
    strata = collections.defaultdict(list)
    for r in per_method_rows:
        if r["additional"] == "yes":
            strata[r["et_category"]].append(r)
    sample = []
    for cat in sorted(strata):
        pop = sorted(strata[cat], key=lambda r: (r["app"], r["method"]))
        k = min(STRATUM_SIZE.get(cat, args.per_stratum), len(pop))
        # Second-level stratification by app: proportional, at least one per app.
        by_app = collections.defaultdict(list)
        for r in pop:
            by_app[r["app"]].append(r)
        alloc = {a: max(1, round(k * len(rs) / len(pop))) for a, rs in by_app.items()}
        while sum(alloc.values()) > k:
            alloc[max(alloc, key=lambda a: alloc[a])] -= 1
        for a in sorted(by_app):
            for r in rng.sample(by_app[a], min(alloc[a], len(by_app[a]))):
                sample.append(dict(stratum=cat, stratum_population=len(pop), **r,
                                   manual_verdict="", manual_evidence=""))
    write("validation_sample.csv", sample)

    if unparsed:
        print("WARNING: %d unparsed EchoTrace lines (first: %s)" % (len(unparsed), unparsed[0]))
    print("strata population:", {k: len(v) for k, v in sorted(strata.items())})
    print("sample size:", len(sample))
    for r in summary_rows:
        print(r["app"], {k: r[k] for k in ("denominator", "et_accounted", "et_mapped", "sw_mapped",
                                         "et_not_found", "et_auto_fail", "sw_auto_fail")})


if __name__ == "__main__":
    main()
