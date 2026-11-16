#!/usr/bin/env python3
"""Mapping populations behind Table II (JDK 8 set) and Table III (latest set), one record per mapping
(image, Java method, native symbol, library file). Imported by sample.py; run alone to print stratum sizes."""
import glob, os, re
from collections import defaultdict

HOME = os.path.expanduser("~")
J8 = f"{HOME}/Tutorial/EchoTrace/Final_results_JDK8"
LT = f"{HOME}/Tutorial/EchoTrace_latest/Final_results_latest_versions_rta"
UN = f"{HOME}/Tutorial/EchoTrace_latest/unavailable_libs"
SETS = {"jdk8": (J8, sorted(os.path.basename(p) for p in glob.glob(f"{J8}/*-jdk8-buster"))),
        "latest": (LT, sorted(os.path.basename(p) for p in glob.glob(f"{LT}/*_*") if not os.path.basename(p).startswith("_")))}
LINE = re.compile(r"^(?:(\S+?):)?([\w.$]+) -> (\S+) \[([^\]]+)\](.*)$")
STRATA = {1: "explicit registration", 2: "name heuristic / bridge", 3: "JNA", 4: "JNR-FFI", 5: "FFM",
          6: "manual / supplied library", 7: "control: JNI symbol lookup"}
TAG_STRATUM = {"JNI_DYNAMIC": 1, "REGISTERED": 1, "NETTY": 2, "DIRECT_LIBC_BRIDGE": 2, "SIGAR_LIST_BRIDGE": 2,
               "DIRECT_JNI_BRIDGE": 2, "SOURCE_JNI_BRIDGE": 2, "UNSAFE_LOCAL_SYMBOL": 2}


def resolve_lib(prefix, setname, root, t, manual):
    """library file a mapping line names (None if not found)"""
    cands = []
    if prefix.startswith("/"):
        cands.append(prefix)
    elif prefix.startswith("LIBS_"):
        cands += [f"{root}/{t}/Dataset/{prefix}", f"{root}/{t}/Dataset_symbolized/{prefix}"]
    elif prefix.startswith("unavailable_libs/"):
        cands.append(f"{HOME}/Tutorial/EchoTrace_latest/{prefix}")
    elif prefix.startswith("notfound_search/"):
        cands += [f"{UN}/{prefix}", f"{UN}/jdk8_{prefix}"]
    cands += [f"{UN}/{t}/{prefix}", f"{root}/{t}/Dataset_symbolized/LIBS_{t}/_supplied/{prefix}",
              f"{root}/{t}/Dataset/LIBS_{t}/{prefix}"]
    for c in cands:
        if os.path.isfile(c):
            return os.path.realpath(c)
    b = os.path.basename(prefix)
    for c in sorted(glob.glob(f"{UN}/{t}/**/{b}", recursive=True)) + \
            sorted(glob.glob(f"{root}/{t}/Dataset/LIBS_{t}/**/{b}", recursive=True)):
        if os.path.isfile(c):
            return os.path.realpath(c)
    return None


def native_methods(o):
    return {l.split()[0] for l in open(f"{o}/native_methods.txt") if l.strip()}


def mapping_records():
    """records from the JNI mapper's output (main and manual)"""
    recs = []
    for setname, (root, imgs) in SETS.items():
        for t in imgs:
            o = f"{root}/{t}/Bytecode_Analysis/outputs_{t}"
            nm = native_methods(o)
            mdir = f"{UN}/{t}/mapping" + ("_rta" if setname == "latest" else "")
            if setname == "latest" and not os.path.isdir(mdir):
                mdir = f"{UN}/{t}/mapping"
            for src, p, manual in (("mapper", f"{o}/mapped_method_syscalls.txt", False),
                                   ("manual", f"{mdir}/mapped_method_syscalls.txt", True)):
                if not os.path.exists(p):
                    continue
                seen = set()
                for l in open(p, errors="replace"):
                    m = LINE.match(l.strip())
                    if not m:
                        continue
                    prefix, meth, sym, tag, rest = m.groups()
                    tag = tag.strip()
                    if "?" in tag or "NOT_FOUND" in tag or meth not in nm:
                        continue
                    key = (prefix, meth, sym)
                    if key in seen:
                        continue
                    seen.add(key)
                    recs.append(dict(set=setname, img=t, src=src, tag=tag, java=meth, sym=sym, libref=prefix or "",
                                     lib=resolve_lib(prefix or "", setname, root, t, manual), note=rest.strip()))
    return recs


def hit_rows(o):
    p = f"{o}/jna_hits.txt"
    if not os.path.exists(p):
        return []
    return [[x.strip() for x in l.split("|")] for l in open(p, errors="replace").readlines()[2:]
            if len(l.split("|")) >= 4]


def binding_records():
    """JNA / JNR-FFI / FFM bindings from the binding detector (jna_hits.txt), resolved only"""
    recs = []
    for setname, (root, imgs) in SETS.items():
        for t in imgs:
            o = f"{root}/{t}/Bytecode_Analysis/outputs_{t}"
            ovr = {}
            op = f"{UN}/{t}/binding_overrides.tsv"
            if t.startswith("jruby_9.4") and not os.path.exists(op):
                op = f"{UN}/jruby_10.1.0.0/binding_overrides.tsv"   # same JNR-FFI classes; as Table II's 33
            if os.path.exists(op):
                for l in open(op):
                    g = l.rstrip("\n").split("\t")
                    ovr[tuple(g[:4])] = g[4]
            ffm_seen = set()
            for f in hit_rows(o):
                det = f[0]
                if det not in ("directmap", "iface", "dyn", "jnr-ffi", "ffi"):
                    continue
                if det == "ffi" and not (t.startswith("tomcat_11") or t.startswith("zookeeper_3.9")):
                    continue        # false FFM (class-name fallback in JARs that never use java.lang.foreign)
                ok = f[2] not in ("<?>", "") and f[3] not in ("<?>", "")
                how = "detector"
                if not ok:
                    if ovr.get(tuple(f[:4])) != "mapped":
                        continue
                    how = "binding_overrides.tsv: mapped"
                stratum = {"jnr-ffi": 4, "ffi": 5}.get(det, 3)
                if det == "ffi":
                    if f[3] in ffm_seen:
                        continue
                    ffm_seen.add(f[3])
                recs.append(dict(set=setname, img=t, src="binding detector", tag=det, java=f[1], sym=f[3],
                                 libref=f[2], lib=None, note=" | ".join(f[4:]), how=how, stratum=stratum, row=f))
    return recs


def strata():
    S = defaultdict(list)
    other = defaultdict(int)
    for r in mapping_records():
        if r["src"] == "manual":
            S[6].append(r)
        elif r["tag"] in TAG_STRATUM:
            S[TAG_STRATUM[r["tag"]]].append(r)
        elif r["tag"] == "JNI" and r["sym"].startswith("Java_"):
            S[7].append(r)
        else:
            other[r["tag"]] += 1
    for r in binding_records():
        S[r["stratum"]].append(r)
    return S, other


if __name__ == "__main__":
    S, other = strata()
    for k in sorted(S):
        by = defaultdict(int)
        for r in S[k]:
            by[r["set"]] += 1
        nolib = sum(1 for r in S[k] if r["src"] != "binding detector" and not r["lib"])
        print(k, STRATA[k], len(S[k]), dict(by), "no lib file:", nolib)
    print("not in any stratum:", dict(other))
