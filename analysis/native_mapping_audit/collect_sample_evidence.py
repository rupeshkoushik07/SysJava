#!/usr/bin/env python3
"""
Attach independent evidence to every row of out/validation_sample.csv so each
SysJava-only result can be adjudicated by hand.

Evidence columns added:
  java_native_descriptors  descriptors of the Java `native` declaration(s), read
                           from the class files in the container's own JARs
  table_rows               RegisterNatives rows (signature|symbol) recovered from
                           the container binaries for this Java method
  signature_match          yes if a table row's signature equals a javap
                           descriptor (overload-exact); "n/a" if no table row
  lib_loaded_at_runtime    the mapped library's basename appears in the sysdig
                           openat trace (libs_loaded_raw.txt)
  jni_symbol_elsewhere     for platform-excluded rows: a Linux .so in the image
                           that exports the method's Java_ symbol (would make the
                           exclusion wrong)

Writes out/validation_sample_evidence.csv.
"""
import csv
import functools
import glob
import os
import re
import struct
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audit_native_mapping import defined_symbols, expected_jni_symbol  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")


def app_dirs():
    with open(os.path.join(OUT, "per_app_summary.csv")) as f:
        return {r["app"]: r["source_dir"] for r in csv.DictReader(f)}


@functools.lru_cache(maxsize=None)
def class_index(app_dir):
    idx = {}
    app = os.path.basename(app_dir)
    # Rebuilt temurin8 images keep their JDK runtime at ~/Prototype/RUNTIME_<app>.
    prototype = os.path.dirname(os.path.dirname(app_dir))
    jars = []
    for d in (os.path.join(app_dir, "Dataset", "RUNTIME_" + app),
              os.path.join(prototype, "RUNTIME_" + app),
              os.path.join(app_dir, "Dataset", "JARFILES_" + app)):
        jars += glob.glob(os.path.join(d, "**", "*.jar"), recursive=True)
    for jar in jars:
        try:
            with zipfile.ZipFile(jar) as z:
                for n in z.namelist():
                    if n.endswith(".class"):
                        # java.base.jar style module images prefix entries with classes/
                        key = n[len("classes/"):] if n.startswith("classes/") else n
                        idx.setdefault(key[:-6].replace("/", "."), (jar, n))
        except Exception:
            pass
    return idx


ACC_NATIVE = 0x0100


@functools.lru_cache(maxsize=None)
def javap_natives(jar, entry):
    """{method_name: [descriptor, ...]} for native methods in one class file.
    Reads the class file directly (equivalent to `javap -s -p`, but in-process)."""
    with zipfile.ZipFile(jar) as z:
        data = z.read(entry)
    u2 = lambda o: struct.unpack_from(">H", data, o)[0]
    u4 = lambda o: struct.unpack_from(">I", data, o)[0]
    pos, n, utf8, i = 10, u2(8), {}, 1
    while i < n:
        tag = data[pos]
        if tag == 1:
            ln = u2(pos + 1)
            utf8[i] = data[pos + 3:pos + 3 + ln].decode("utf-8", "replace")
            pos += 3 + ln
        elif tag in (3, 4, 9, 10, 11, 12, 17, 18):
            pos += 5
        elif tag in (5, 6):
            pos += 9
            i += 1
        elif tag in (7, 8, 16, 19, 20):
            pos += 3
        elif tag == 15:
            pos += 4
        else:
            raise ValueError("bad constant pool tag %d in %s" % (tag, entry))
        i += 1
    pos += 6                                   # access_flags, this_class, super_class
    pos += 2 + 2 * u2(pos)                     # interfaces

    def members(p):
        """Return ([(flags, name, descriptor)], end_offset) for a fields/methods table."""
        out, count, p = [], u2(p), p + 2
        for _ in range(count):
            out.append((u2(p), utf8[u2(p + 2)], utf8[u2(p + 4)]))
            attrs, p = u2(p + 6), p + 8
            for _ in range(attrs):
                p += 6 + u4(p + 2)
        return out, p

    _, pos = members(pos)                      # fields
    res = {}
    for flags, name, desc in members(pos)[0]:  # methods
        if flags & ACC_NATIVE:
            res.setdefault(name, []).append(desc)
    return res


def jni_overload_params(sym, method):
    """Decode the `__<sig>` suffix of a JNI long name into a parameter descriptor.
    The short name is stripped first: `__1x` inside it is an escaped `_x`."""
    short = expected_jni_symbol(method)
    if not sym.startswith(short + "__"):
        return None
    mangled = sym[len(short) + 2:]
    out, i = [], 0
    while i < len(mangled):
        c = mangled[i]
        if c == "_" and i + 1 < len(mangled):
            nxt = mangled[i + 1]
            if nxt == "1":
                out.append("_"); i += 2; continue
            if nxt == "2":
                out.append(";"); i += 2; continue
            if nxt == "3":
                out.append("["); i += 2; continue
            if nxt == "0":
                out.append(chr(int(mangled[i + 2:i + 6], 16))); i += 6; continue
            out.append("/"); i += 1; continue
        out.append(c)
        i += 1
    return "(" + "".join(out) + ")"


def java_descriptors(app_dir, method):
    cls, _, name = method.rpartition(".")
    hit = class_index(app_dir).get(cls)
    if not hit:
        return None
    return javap_natives(*hit).get(name, [])


@functools.lru_cache(maxsize=None)
def table(app_dir):
    app = os.path.basename(app_dir)
    rows = {}
    bdir = os.path.join(app_dir, "Bytecode_Analysis", "outputs_" + app)
    for fn in ("jvm_dynamic_mapping.txt", "jni_dynamic_bindings.txt"):
        p = os.path.join(bdir, fn)
        if not os.path.isfile(p):
            continue
        for line in open(p, encoding="utf-8", errors="replace"):
            if line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("|")
            if len(parts) >= 4:
                rows.setdefault(parts[1], []).append((parts[0], parts[2], parts[3]))
    return rows


@functools.lru_cache(maxsize=None)
def loaded_libs(app_dir):
    names = set()
    for p in glob.glob(os.path.join(app_dir, "Dynamic_Analysis", "*", "libs_loaded_raw.txt")):
        for line in open(p, encoding="utf-8", errors="replace"):
            for tok in line.split():
                if ".so" in tok:
                    names.add(os.path.basename(tok))
    return names


@functools.lru_cache(maxsize=None)
def all_libs(app_dir):
    app = os.path.basename(app_dir)
    root = os.path.join(app_dir, "Dataset", "LIBS_" + app)
    out = []
    for r, _, files in os.walk(root):
        out += [os.path.join(r, f) for f in files if ".so" in f and not f.endswith(".lck")]
    return out


def population_checks(dirs):
    """Whole-population passes that do not need a human:
    - overload check for every table-backed mapping (REGISTERED/JVM/JNI_DYNAMIC)
    - declarations per denominator entry (native_methods.txt lists class.method
      names, so overloads collapse into one entry)."""
    with open(os.path.join(OUT, "per_method.csv")) as f:
        rows = list(csv.DictReader(f))
    stats = {}
    bad = []
    for r in rows:
        d = dirs[r["app"]]
        s = stats.setdefault(r["app"], dict(app=r["app"], names=0, names_found=0, declarations=0,
                                            overloaded_names=0, table_mappings=0,
                                            sig_checked=0, sig_mismatch=0,
                                            jni_overload_checked=0, jni_overload_mismatch=0))
        descs = java_descriptors(d, r["method"])
        s["names"] += 1
        if descs is not None:
            s["names_found"] += 1
            s["declarations"] += max(1, len(descs))
            s["overloaded_names"] += len(descs) > 1
        if r["et_tag"] == "JNI" and descs:
            params = jni_overload_params(r["et_symbol"], r["et_alias"] or r["method"])
            if params is not None:
                s["jni_overload_checked"] = s.get("jni_overload_checked", 0) + 1
                if not any(dd.startswith(params) for dd in descs):
                    s["jni_overload_mismatch"] = s.get("jni_overload_mismatch", 0) + 1
                    bad.append(dict(app=r["app"], method=r["method"], mapped_symbol=r["et_symbol"],
                                    mapped_signature=params, java_descriptors=" ".join(descs),
                                    correct_symbols="(JNI long name; no matching overload)"))
        if r["et_tag"] not in ("REGISTERED", "JVM", "JNI_DYNAMIC"):
            continue
        s["table_mappings"] += 1
        m = r["et_alias"] or r["method"]
        unshaded = re.sub(r"^.+?\.io\.netty\.", "io.netty.", m)
        trows = table(d).get(r["method"]) or table(d).get(m) or table(d).get(unshaded) or []
        chosen = [t for t in trows if t[2] == r["et_symbol"]]
        if not descs or not chosen:
            continue
        s["sig_checked"] += 1
        if not any(t[1] in descs for t in chosen):
            s["sig_mismatch"] += 1
            right = [t[2] for t in trows if t[1] in descs]
            bad.append(dict(app=r["app"], method=r["method"], mapped_symbol=r["et_symbol"],
                            mapped_signature=" ".join(t[1] for t in chosen),
                            java_descriptors=" ".join(descs),
                            correct_symbols=" ".join(right)))
    with open(os.path.join(OUT, "overload_check.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(next(iter(stats.values())).keys()))
        w.writeheader()
        w.writerows(stats.values())
    with open(os.path.join(OUT, "overload_mismatches.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["app", "method", "mapped_symbol", "mapped_signature",
                                          "java_descriptors", "correct_symbols"])
        w.writeheader()
        w.writerows(bad)
    print("overload mismatches:", len(bad))


def main():
    dirs = app_dirs()
    population_checks(dirs)
    with open(os.path.join(OUT, "validation_sample.csv")) as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        d = dirs[r["app"]]
        m = r["et_alias"] or r["method"]
        unshaded = re.sub(r"^.+?\.io\.netty\.", "io.netty.", m)
        descs = java_descriptors(d, r["method"])
        r["java_native_descriptors"] = "class-not-found" if descs is None else " ".join(descs)
        trows = table(d).get(r["method"]) or table(d).get(m) or table(d).get(unshaded) or []
        r["table_rows"] = " ; ".join("%s|%s|%s" % t for t in trows)
        if not trows:
            r["signature_match"] = "n/a"
        elif descs:
            r["signature_match"] = "yes" if any(t[1] in descs and t[2] == r["et_symbol"] for t in trows) else "no"
        else:
            r["signature_match"] = "unknown"
        params = jni_overload_params(r["et_symbol"], r["et_alias"] or r["method"]) if r["et_tag"] == "JNI" else None
        if params is not None and descs:
            r["signature_match"] = "yes" if any(dd.startswith(params) for dd in descs) else "no"
        r["lib_loaded_at_runtime"] = ("yes" if r["et_lib"] and r["et_lib"] in loaded_libs(d)
                                      else ("no" if r["et_lib"] else ""))
        if r["et_category"] == "platform":
            sym = expected_jni_symbol(r["method"])
            hits = [os.path.basename(p) for p in all_libs(d)
                    if any(s == sym or s.startswith(sym + "__") for s in defined_symbols(p))]
            r["jni_symbol_elsewhere"] = " ".join(hits)
        else:
            r["jni_symbol_elsewhere"] = ""
    fields = list(rows[0].keys())
    for k in ("manual_verdict", "manual_evidence"):
        fields.remove(k)
        fields.append(k)
    with open(os.path.join(OUT, "validation_sample_evidence.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print("wrote %d rows" % len(rows))


if __name__ == "__main__":
    main()
