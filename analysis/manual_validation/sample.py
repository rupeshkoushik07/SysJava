#!/usr/bin/env python3
"""Stratified random sample of SysJava's resolved mappings for manual validation (requirement R6).

Population (population.py): every resolved mapping behind Table II (Final_results_JDK8, 10 images) and Table III
(Final_results_latest_versions_rta, 10 images); one record = (image, Java method or binding, native function,
library file). Strata:
  1 explicit registration  JNI_DYNAMIC, REGISTERED, and JVM-tagged mappings whose (method, symbol) is in the
                           image's jvm_dynamic_mapping.txt (RegisterNatives tables scanned from the binaries)
  2 name heuristic/bridge  NETTY, DIRECT_LIBC_BRIDGE, SIGAR_LIST_BRIDGE, and JVM-tagged mappings from the mapper's
                           built-in JVM_* name table
  3 JNA, 4 JNR-FFI         binding-detector hits (jna_hits.txt) with library and function recovered, or classified
                           "mapped" in unavailable_libs/<t>/binding_overrides.tsv (JDK 8 JRuby: the 10.1.0.0 file,
                           as for Table II)
  5 FFM                    Tomcat 11 and ZooKeeper 3.9.5 ffi hits, one per symbol
  6 manual / supplied      resolved lines of unavailable_libs/<t>/mapping{,_rta}/mapped_method_syscalls.txt
  7 control                JNI-tagged mappings to a Java_* symbol (exact JNI symbol lookup)
Sample: SEED below; per stratum, the population is shuffled, grouped by image, and drawn round-robin over the images
(in shuffled order) until N, so the draw spreads across images where possible.
Writes sample.tsv, sample.md, population_sizes.tsv next to this script.
"""
import csv, glob, os, random, re, sys
from collections import OrderedDict, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import population as P
from elfev import elf, jni_mangle, jni_short_name, sha16, symbolized

SEED, N = 20261116, 20
H = os.path.dirname(os.path.abspath(__file__))
TUT = os.path.expanduser("~/Tutorial") + "/"
WIN = {"kernel32", "msvcrt", "winmm", "advapi32", "user32", "psapi"}


def rel(p):
    return p.replace(TUT, "~/Tutorial/") if p else ""


def out_dir(r):
    root = P.SETS[r["set"]][0]
    return f"{root}/{r['img']}/Bytecode_Analysis/outputs_{r['img']}"


def libs_dir(r):
    root = P.SETS[r["set"]][0]
    return f"{root}/{r['img']}/Dataset/LIBS_{r['img']}"


def table_rows(path):
    """pipe files: lib|class.method|signature|symbol|confidence"""
    rows = []
    if os.path.exists(path):
        for l in open(path, errors="replace"):
            if l.startswith("#") or l.count("|") < 4:
                continue
            rows.append(l.rstrip("\n").split("|"))
    return rows


def find_lib(r, base):
    for p in sorted(glob.glob(f"{libs_dir(r)}/**/{base}", recursive=True)):
        if os.path.isfile(p):
            return os.path.realpath(p)
    return None


# ---------------------------------------------------------------- strata
def build():
    S, other = P.strata()
    jvmdyn = {}
    for (root, imgs), setname in ((P.SETS[k], k) for k in P.SETS):
        for t in imgs:
            o = f"{root}/{t}/Bytecode_Analysis/outputs_{t}"
            jvmdyn[(setname, t)] = {(x[1], x[3]) for x in table_rows(f"{o}/jvm_dynamic_mapping.txt")}
    for r in P.mapping_records():
        if r["src"] == "mapper" and r["tag"] == "JVM":
            (S[1] if (r["java"], r["sym"]) in jvmdyn[(r["set"], r["img"])] else S[2]).append(dict(r, jvmsrc=True))
    for k in S:
        for r in S[k]:
            r["stratum"] = k
    return S


def draw(pop, rng):
    pop = list(pop)
    rng.shuffle(pop)
    groups = OrderedDict()
    for r in pop:
        groups.setdefault((r["set"], r["img"]), []).append(r)
    keys = list(groups)
    rng.shuffle(keys)
    out = []
    while len(out) < N and any(groups[k] for k in keys):
        for k in keys:
            if groups[k] and len(out) < N:
                out.append(groups[k].pop(0))
    return out


# ---------------------------------------------------------------- evidence
def sym_ev(lib, sym):
    if not lib:
        return None, "library file not found"
    e = elf(symbolized(lib))
    how, line = e.sym_line(sym)
    return how, (f"{how}: {line}" if how else f"{sym} not defined in {os.path.basename(lib)}")


def reg_entries(lib, meth, sym, fnlib):
    """JNINativeMethod entries named <meth> in <lib>; (matching, others)"""
    e = elf(symbolized(lib))
    target = elf(symbolized(fnlib)).addr(sym) if fnlib else None
    same = os.path.realpath(lib) == os.path.realpath(fnlib or "")
    match, other = [], []
    for o, n, sig, fn in e.jni_tables().get(meth, []):
        ok = (fn == sym) or (same and isinstance(fn, int) and fn == target)
        fs = fn if isinstance(fn, str) else f"0x{fn:x}" + (f" ({', '.join(e.by_addr.get(fn, [])[:2])})" if e.by_addr.get(fn) else "")
        txt = f"{os.path.basename(lib)} vaddr 0x{o:x} (file offset 0x{e.file_off(o):x}): {{\"{n}\", \"{sig}\", {fs}}}"
        (match if ok else other).append(txt)
    return match, other


def ev_registration(r):
    o = out_dir(r) if r["src"] == "mapper" else os.path.dirname(P.UN + f"/{r['img']}/x")
    meth = r["java"].rsplit(".", 1)[1]
    tbl_libs = []
    src_rows = []
    for f in ("jni_dynamic_bindings.txt", "jvm_dynamic_mapping.txt"):
        for x in table_rows(f"{out_dir(r)}/{f}"):
            if x[1] == r["java"] and x[3] == r["sym"]:
                src_rows.append(f"{f}: {'|'.join(x[:5])}")
                b = x[0].split("/")[-1]
                p = r["lib"] if r["lib"] and os.path.basename(r["lib"]) == b else find_lib(r, b)
                if p and p not in tbl_libs:
                    tbl_libs.append(p)
    if r["lib"] and r["lib"] not in tbl_libs:
        tbl_libs.append(r["lib"])
    how, sline = sym_ev(r["lib"], r["sym"])
    match, other = [], []
    for tl in tbl_libs:
        m, x = reg_entries(tl, meth, r["sym"], r["lib"])
        match += m
        other += x
    ev = [sline] + src_rows[:1]
    if match:
        ev.append("RegisterNatives entry: " + match[0])
        v = ("correct", f"decoded JNINativeMethod entry names {meth} and points to {r['sym']}")
    elif other:
        ev.append("entries named " + meth + " point elsewhere: " + "; ".join(other[:2]))
        v = ("incorrect?", f"no {meth} entry points to {r['sym']}")
    elif how:
        v = ("unverifiable", f"no static JNINativeMethod entry named {meth} (table built at run time); symbol exists")
    else:
        v = ("incorrect?", "symbol not in library")
    return ev, v


def start_module(r):
    """(name_addr, module) the pipeline's SysPart run of the mapped library used for start <sym>"""
    root = P.SETS[r["set"]][0]
    d = f"{root}/{r['img']}/Binary_Analysis/syscalls_output_{r['img']}/{os.path.basename(r['lib'])}"
    if not os.path.exists(d + "/startfuncs_with_addr.txt"):
        return None
    for x in open(d + "/startfuncs_with_addr.txt"):
        n, a = x.strip().rsplit("_", 1) if "_" in x.strip() else (x.strip(), "")
        if n != r["sym"]:
            continue
        for l in open(d + "/allfunctions.txt"):
            q = l.split()
            if len(q) >= 3 and q[0] == n and q[1] == a:
                return f"{n} at 0x{a}", re.sub(r".*/|^module-", "", q[2])
    return None


def ev_heuristic(r):
    meth = r["java"].rsplit(".", 1)[1]
    how, sline = sym_ev(r["lib"], r["sym"])
    ev = [sline]
    tag = r["tag"]
    if tag == "NETTY":
        m, x = reg_entries(r["lib"], meth, r["sym"], r["lib"]) if r["lib"] else ([], [])
        ev.append(f"rule: Netty symbol naming (netty_<module>_<class>_<method>) for {r['java']}")
        if m:
            ev.append("RegisterNatives entry: " + m[0])
            return ev, ("correct", "name rule confirmed by the library's JNINativeMethod table")
        if x:
            ev.append("entries named " + meth + ": " + "; ".join(x[:2]))
            return ev, ("incorrect?", "table entry with this name points to another function")
        ok = how is not None and r["sym"].endswith("_" + meth)
        return ev, (("correct" if ok else "unverifiable"),
                    "symbol exists and ends with the Java method name; no static table entry" if ok else "no table entry")
    if tag == "DIRECT_LIBC_BRIDGE":
        ev.append(f"rule: JNA direct-mapped native {r['java']} calls the libc function of the same name")
        if how is None and r["lib"]:
            for c in image_lib(r, "c"):
                h2, l2 = sym_ev(c, r["sym"])
                if h2:
                    ev.append(f"{os.path.basename(c)} {l2}")
            mod = start_module(r)
            if mod:
                ev.append(f"pipeline SysPart run of {os.path.basename(r['lib'])}: start {r['sym']} resolves to {mod[0]} in {mod[1]}")
            if mod and mod[1].startswith("libc"):
                return ev, ("correct", f"library recorded as an importing library ({os.path.basename(r['lib'])}); function resolves to "
                                       f"libc's {r['sym']} in the dependency graph; syscalls unaffected")
            return ev, ("incorrect", f"wrong library: {r['sym']} is attributed to {os.path.basename(r['lib'])}, which only imports it" +
                                      (f"; its run starts at {mod[1]}'s {r['sym']}" if mod else "; its run does not start from it"))
        ok = how == "nm -D" and r["sym"] == meth
        return ev, (("correct" if ok else "incorrect?"), "exported libc function with the Java method's name" if ok else "name/export mismatch")
    if tag == "SIGAR_LIST_BRIDGE":
        ev.append(f"rule: Sigar bridge table {r['java']} -> {r['sym']} (the Java list/gather method calls this JNI function)")
        return ev, (("correct" if how else "incorrect?"), "bridge target exists in libsigar" if how else "bridge target missing")
    if tag == "JVM":
        ev.append(f"rule: mapper's built-in table JVM_BUILTIN_NATIVES: {r['java']} -> {r['sym']} (libjava registers it; HotSpot export)")
        return ev, (("correct" if how else "incorrect?"), "libjvm defines the JVM_* function" if how else "not in libjvm")
    return ev, ("unverifiable", f"no rule for tag {tag}")


OTHER_OS_CLASS = re.compile(r"(\.freebsd\.|\.osx\.|\.mac\.|Darwin|MacLibrary|Solaris|Windows|Win32|WinLibC|Kernel32|MSVCRT)")
BSD_FUNCS = {"kevent", "kqueue"}


def image_lib(r, base):
    """library file lib<base>.so* in the image (shortest name first)"""
    cands = [p for p in glob.glob(f"{libs_dir(r)}/**/*", recursive=True)
             if os.path.isfile(p) and re.match(rf"^lib{re.escape(base)}([-.]|\.so)", os.path.basename(p))
             and ".so" in os.path.basename(p)]
    cands = [c for c in set(os.path.realpath(c) for c in cands) if open(c, "rb").read(4) == b"\x7fELF"]
    return sorted(cands, key=lambda p: (len(os.path.basename(p)), p))


def binding_lib(r):
    """(library file exporting the function or None, how, note)"""
    ref = r["libref"].split("|")[0].strip()
    names = [x.strip().lower() for x in r["libref"].split("|")]
    if any(n in WIN for n in names) and not any(n.startswith("libc") or n == "c" for n in names):
        return None, "", "Windows library"
    if ref in ("<?>", "socket", "c") or ref.startswith("libc.so") or r["how"] != "detector":
        base = "c"
    else:
        base = re.sub(r"^lib", "", re.sub(r"\.so.*$", "", ref))
    cands = image_lib(r, base)
    for c in cands:
        e = elf(c)
        if r["sym"] in e.dyn:
            return c, "", ""
        for dep in e.needed:          # dlsym on the library handle also searches its dependencies
            for d in image_lib(r, re.sub(r"^lib", "", re.sub(r"\.so.*$", "", dep))):
                if r["sym"] in elf(d).dyn:
                    return d, f"exported by {os.path.basename(d)}, a DT_NEEDED dependency of {os.path.basename(c)} (dlsym on the {os.path.basename(c)} handle resolves it)", ""
    if r["tag"] == "ffi" and base != "c":    # SymbolLookup chains (library lookup .or(default lookup)) end in libc
        for c in image_lib(r, "c"):
            if r["sym"] in elf(c).dyn:
                return c, f"not in lib{base} ({'absent from the image' if not cands else 'not exported'}); exported by {os.path.basename(c)} (Linker default lookup)", ""
    return (cands[0] if cands else None), "", ("not exported by " + os.path.basename(cands[0]) if cands else f"no lib{base} in the image")


def ev_binding(r):
    f = r["row"]
    det = f[0]
    if det == "ffi":
        site = f"{f[1]} via {f[4] if len(f) > 4 else ''} ({f[5] if len(f) > 5 else ''})"
    elif det in ("iface", "dyn"):
        site = f"call site {f[1]}; {f[4] if len(f) > 4 else ''}; interface method {f[6] if len(f) > 6 else ''}"
    elif det == "jnr-ffi":
        site = f"interface {f[1]} loaded with {f[4] if len(f) > 4 else ''} ({f[5] if len(f) > 5 else ''})"
    else:
        site = f"native {f[1]}; {f[4] if len(f) > 4 else ''} ({f[5] if len(f) > 5 else ''})"
    lib, how, why = binding_lib(r)
    r["lib"] = lib
    ev = [f"detector row: {det} | lib '{r['libref']}' | symbol {r['sym']}" + (f" ({r['how']})" if r["how"] != "detector" else ""), site]
    javaside = " ".join(f[1:2] + f[5:7])
    if lib and r["sym"] in elf(lib).dyn:
        v, l = elf(lib).dyn[r["sym"]]
        ev.append(f"nm -D {os.path.basename(lib)}: {v:016x} {l} {r['sym']}" + (f" — {how}" if how else ""))
        if OTHER_OS_CLASS.search(javaside):
            return ev, ("unverifiable", "other-OS binding (class for another OS); the Linux library happens to export the name")
        if how and "default lookup" in how:
            return ev, ("correct (library note)", "function correct; the detector's library name is imprecise (" + how.split(";")[0] + ")")
        return ev, ("correct", "library in the image exports the bound function" + (" through a dependency" if how else ""))
    if why == "Windows library" or OTHER_OS_CLASS.search(javaside) or r["sym"] in BSD_FUNCS:
        ev.append(why or "not in the Linux libraries")
        return ev, ("unverifiable", "other-OS binding (" + ("Windows library" if why == "Windows library" else
                                    "BSD/macOS function" if r["sym"] in BSD_FUNCS else "class for another OS") + "); not in a Linux image")
    ev.append(why)
    if "openssl_h_Macros" in f[1] or "openssl_h_Compatibility" in f[1]:
        ev.append("bytecode: the downcall is taken only for another SSL library (openssl_h_Macros: if BORINGSSL, else the "
                  "macro via SSL_CTX_ctrl; openssl_h_Compatibility: OpenSSL 1.x / LibreSSL names, e.g. EVP_PKEY_bits = "
                  "EVP_PKEY_get_bits in OpenSSL 3)")
        return ev, ("unverifiable", "version-conditional binding (BoringSSL / OpenSSL 1.x name); the image's OpenSSL 3 does not export it and Tomcat does not call it there")
    return ev, ("incorrect?", f"function not exported in this image ({why})")


def provenance(r):
    rows = [l.rstrip("\n").split("\t") for l in open(f"{P.UN}/PROVENANCE.tsv")][1:]
    b = os.path.basename(r["lib"] or "")
    for x in rows:
        if x[0] == r["img"] and (x[1] == b or b.startswith(x[1].split(".so")[0])):
            return x
    return None


def notes_line(r):
    d = os.path.basename(os.path.dirname(r["lib"] or ""))
    b = os.path.basename(r["lib"] or "")
    for key in (d, b.split(".so")[0]):
        for l in open(f"{P.UN}/NOTES.md", errors="replace"):
            if key and key in l and ("built" in l or "from" in l):
                return l.strip()[:300]
    return ""


def ev_manual(r):
    meth = r["java"].rsplit(".", 1)[1]
    how, sline = sym_ev(r["lib"], r["sym"])
    ev = [f"manual mapping line ({rel(r['libref']) or 'no lib'}) [{r['tag']}]", sline]
    pv = provenance(r)
    inimg = r["lib"] and f"/{r['img']}/Dataset" in r["lib"]
    if pv:
        ev.append(f"provenance: {pv[3]} — {pv[4]}")
    elif inimg:
        ev.append("library is the image's own file (mapped in the supplement run)")
    else:
        ev.append(f"library: {rel(r['lib'])} (no PROVENANCE.tsv row)")
    if r["tag"] in ("REGISTERED", "JNI_DYNAMIC") and r["lib"]:
        m, x = reg_entries(r["lib"], meth, r["sym"], r["lib"])
        if m:
            ev.append("RegisterNatives entry: " + m[0])
    if not how:
        return ev, ("incorrect?", "symbol not in the supplied library")
    sym_ok = True
    if r["tag"] == "JNI" and not r["sym"].startswith("Java_") and os.path.basename(r["lib"] or "").startswith("libc"):
        sym_ok = r["sym"] == meth          # JNA direct-mapped native -> libc function of the same name
        ev.append(f"JNA direct-mapped native: libc function named {meth}: {'match' if sym_ok else 'MISMATCH'}")
    elif r["tag"] == "JNI":
        short = jni_short_name(r["java"])
        sym_ok = r["sym"] == short or r["sym"].startswith(short + "__")
        ev.append(f"expected JNI name {short}: {'match' if sym_ok else 'MISMATCH'}")
    note = (pv[4] if pv else "").lower()
    if not sym_ok:
        return ev, ("incorrect?", "symbol name does not match the Java method")
    if pv and ("not loaded" in note or "cannot load" in note or "never loaded" in note):
        return ev, ("correct (version note)", "function correct; library not loaded by the app at run time (see provenance)")
    if pv and ("lacks" in note or "missing" in note or "2012 build" in note):
        return ev, ("correct (version note)", "function correct; supplied build differs from the version the app ships (see provenance)")
    if not pv and not inimg:
        nl = notes_line(r)
        if nl:
            ev.append("provenance (unavailable_libs/NOTES.md): " + nl)
            return ev, ("correct (version note)", "function correct; supplied library documented in NOTES.md (not shipped by the image)")
        return ev, ("unverifiable", "supplied library without a provenance record")
    return ev, ("correct", "symbol defined in the library of the matching version" if pv else "symbol defined in the image's library")


def ev_control(r):
    short = jni_short_name(r["java"])
    how, sline = sym_ev(r["lib"], r["sym"])
    ok = r["sym"] == short or r["sym"].startswith(short + "__")
    ev = [f"expected short name {short}" + (" (overloaded form: + __<mangled args>)" if r["sym"] != short else ""), sline]
    if ok and how:
        return ev, ("correct", "mangled name matches and the library defines it")
    return ev, ("incorrect?", "mangled name mismatch" if not ok else "symbol not defined")


EV = {1: ev_registration, 2: ev_heuristic, 3: ev_binding, 4: ev_binding, 5: ev_binding, 6: ev_manual, 7: ev_control}


def main():
    rng = random.Random(SEED)
    S = build()
    sizes, rows = [], []
    for k in sorted(P.STRATA):
        pop = S.get(k, [])
        by = defaultdict(int)
        for r in pop:
            by[r["set"]] += 1
        smp = draw(pop, rng)
        sizes.append([k, P.STRATA[k], len(pop), by["jdk8"], by["latest"], len({(r['set'], r['img']) for r in pop}),
                      len(smp), len({(r['set'], r['img']) for r in smp})])
        for i, r in enumerate(smp, 1):
            ev, (verdict, reason) = EV[k](r)
            lib = r["lib"]
            rows.append([f"S{k}-{i:02d}", r["set"], r["img"], k, r["tag"], r["java"], r["sym"], rel(lib),
                         sha16(lib) if lib else "", " || ".join(e for e in ev if e), verdict, reason])
    hdr = ["id", "set", "image", "stratum", "tag", "java_side", "native_function", "library", "sha256_16",
           "evidence", "precheck", "precheck_reason"]
    with open(f"{H}/sample.tsv", "w", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(hdr)
        w.writerows(rows)
    with open(f"{H}/population_sizes.tsv", "w") as f:
        f.write("stratum\tname\tpopulation\tjdk8\tlatest\timages\tsampled\tsampled_images\n")
        for s in sizes:
            f.write("\t".join(map(str, s)) + "\n")
    md = [f"# Manual validation sample (seed {SEED}, {N} per stratum)\n",
          "Population: resolved mappings behind Table II (JDK 8) and Table III (latest). Columns: Java side, chosen "
          "native function and library, the evidence to check, and a pre-check verdict to confirm.\n",
          "| Stratum | Population | JDK 8 | Latest | Images | Sampled | Sampled images | " +
          " | ".join(sorted({r[10] for r in rows})) + " |",
          "|---|---:|---:|---:|---:|---:|---:|" + "---:|" * len({r[10] for r in rows})]
    vs = sorted({r[10] for r in rows})
    for s in sizes:
        c = defaultdict(int)
        for r in rows:
            if r[3] == s[0]:
                c[r[10]] += 1
        md.append(f"| {s[0]} {s[1]} | {s[2]:,} | {s[3]:,} | {s[4]:,} | {s[5]} | {s[6]} | {s[7]} | " +
                  " | ".join(str(c[v]) for v in vs) + " |")
    for s in sizes:
        md.append(f"\n## {s[0]}. {s[1]}\n")
        for r in rows:
            if r[3] != s[0]:
                continue
            md.append(f"**{r[0]}** {r[2]} ({r[1]}) `[{r[4]}]` — **{r[10]}**: {r[11]}  \n"
                      f"Java: `{r[5]}`  \nNative: `{r[6]}` in `{r[7]}` (sha256 {r[8]})  \n"
                      + "  \n".join(f"- {e}" for e in r[9].split(" || ")) + "\n")
    open(f"{H}/sample.md", "w").write("\n".join(md) + "\n")
    for s in sizes:
        print(s)
    c = defaultdict(int)
    for r in rows:
        c[(r[3], r[10])] += 1
    print(dict(c))


if __name__ == "__main__":
    main()
