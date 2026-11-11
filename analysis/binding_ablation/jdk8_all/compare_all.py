#!/usr/bin/env python3
"""Binding vs no binding over all ten JDK 8 images, one row per distinct library file per image.

  Binding     the pipeline's own SysPart run: sysjava_results/<t>/Binary_Analysis/syscalls_output_<t>/<lib>/ (startfuncs_resolved.txt,
              syscalls.txt). Two names for one file (libtcnative-1.so.0 and .0.2.28; Storm's two netty
              names) are one library: starts and syscalls are the union of both runs.
  No binding  SysPart from every function of the library (arm A of run_ablation.sh), run once per
              distinct file (sha256) by make_targets.py / run_all.sh; results/A/<img>/<lib>/startfuncs_with_addr.txt,
              syscalls.txt. libjvm.so: not resolved (std::bad_alloc at 35 and 60 GB on Tomcat 11).
  Profile     final policy (Binary_Analysis/syscalls_output_<t>/<t>.json; Storm tables/storm_no_false_ffm, without the false-FFM sync; the paper's numbers) and the
              same policy with every library's no-binding set added (libjvm keeps its binding set).

Writes results/summary.md, per_library.tsv and per_image.tsv.
"""
import csv, json, os
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
R = os.path.join(ART, "2_swat4j_vs_sysjava", "sysjava_results")
NAMES = {"zookeeper_3.4.14-jdk8-buster": "Apache ZooKeeper 3.4.14", "tomcat_7.0-jdk8-buster": "Apache Tomcat 7.0.109",
         "cassandra_3.0.29-jdk8-buster": "Apache Cassandra 3.0.29", "jetty_9.4.51-jdk8-buster": "Eclipse Jetty 9.4.51",
         "storm_2.4.0-jdk8-buster": "Apache Storm 2.4.0", "orientdb_3.2.19-jdk8-buster": "OrientDB 3.2.19",
         "elasticsearch_7.5.2-jdk8-buster": "Elasticsearch 7.5.2", "solr_8.7.0-jdk8-buster": "Apache Solr 8.7.0",
         "groovy_4.0.0-jdk8-buster": "Apache Groovy 4.0.0", "jruby_9.4.2.0-jdk8-buster": "JRuby 9.4.2.0"}
A_FIX = {}   # make_targets.py names every run after the real file


def lines(p):
    try:
        return {l.split()[0] for l in open(p) if l.strip()}
    except FileNotFoundError:
        return None


rows = list(csv.DictReader(open(f"{HERE}/results/libraries.tsv"), delimiter="\t"))
imgs = OrderedDict()
for r in rows:
    imgs.setdefault(r["img"], OrderedDict()).setdefault(r["sha256_16"], []).append(r)

per_lib, per_img, md = [], [], []
all_only_nb = {}
for img, libs in imgs.items():
    # Storm: the paper's profile, without `sync` from false FFM hits (2_swat4j_vs_sysjava/README.md)
    pp = f"{ART}/2_swat4j_vs_sysjava/tables/storm_no_false_ffm/{img}.json" if img.startswith("storm_") else \
        f"{R}/{img}/Binary_Analysis/syscalls_output_{img}/{img}.json"
    pol = json.load(open(pp))
    final = {n for s in pol["syscalls"] if s["action"] == "SCMP_ACT_ALLOW" for n in s["names"]}
    tb, tnb, sb, snb, nb_add = set(), set(), 0, 0, set()
    md.append(f"\n## {NAMES[img]} (`{img}`)\n\n| Library | Binding: start functions | Binding: syscalls | "
              f"No binding: start functions | No binding: syscalls | Only without binding |\n|---|---:|---:|---:|---:|---|")
    for sha, rs in libs.items():
        name = " = ".join(r["lib"] for r in rs)
        bst, bsc = set(), set()
        for r in rs:
            bst |= lines(f"{ART}/{r['binding_run']}/startfuncs_resolved.txt") or set()
            bsc |= lines(f"{ART}/{r['binding_run']}/syscalls.txt") or set()
        a_img, a_lib = rs[0]["A_run_img"], rs[0]["A_run_lib"]
        a_lib = A_FIX.get((a_img, a_lib), a_lib)
        if rs[0]["lib"] == "libjvm.so":
            ast = asc = None
        else:
            ast = lines(f"{HERE}/results/A/{a_img}/{a_lib}/startfuncs_with_addr.txt")
            asc = lines(f"{HERE}/results/A/{a_img}/{a_lib}/syscalls.txt")
        if asc is None:
            only, lost = None, None
            nb_add |= bsc
            md.append(f"| {name} | {len(bst):,} | {len(bsc)} | not resolved | not resolved | |")
        else:
            only, lost = asc - bsc, bsc - asc
            tb |= bsc; tnb |= asc; sb += len(bst); snb += len(ast); nb_add |= asc
            for s in only:
                all_only_nb.setdefault(s, set()).add(img.split("_")[0])
            md.append(f"| {name} | {len(bst):,} | {len(bsc)} | {len(ast):,} | {len(asc)} | "
                      f"+{len(only)}" + (f" ({', '.join(sorted(only))})" if 0 < len(only) <= 12 else "")
                      + (f"; binding-only {len(lost)}: {', '.join(sorted(lost))}" if lost else "") + " |")
        per_lib.append([img, name, sha, len(bst), len(bsc), "" if ast is None else len(ast),
                        "not resolved" if asc is None else len(asc),
                        "" if only is None else " ".join(sorted(only)),
                        "" if lost is None else " ".join(sorted(lost))])
    prof_nb = final | nb_add
    md.append(f"| **All except libjvm.so** | **{sb:,}** | **{len(tb)}** | **{snb:,}** | **{len(tnb)}** | "
              f"+{len(tnb - tb)} |")
    added = prof_nb - final
    md.append(f"\nProfile: {len(final)} syscalls with binding (final policy); {len(prof_nb)} without binding "
              f"(+{len(added)}: {', '.join(sorted(added)) or 'none'}).")
    per_img.append([img, sum(1 for _ in libs), sb, len(tb), snb, len(tnb), len(final), len(prof_nb),
                    " ".join(sorted(added))])

head = ["# Binding vs no binding: all ten JDK 8 images (static analysis only)\n",
        "Binding = SysPart from the functions the native methods map to (the pipeline's own run). "
        "No binding = SysPart from every function in the library (same file, same SysPart build). "
        "All images: JDK 8u504 (Eclipse Temurin), Debian 10. "
        "libjvm.so without binding is not resolved (out of memory at 35 and 60 GB on Tomcat 11), so the "
        "\"All except libjvm.so\" rows leave it out; for the profile column libjvm keeps its binding set.\n",
        "| Image | Libraries | Binding: start functions | Binding: syscalls | No binding: start functions | "
        "No binding: syscalls | Profile with binding | Profile without binding | Added to profile |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|"]
for r in per_img:
    head.append(f"| {NAMES[r[0]]} | {r[1]} | {r[2]:,} | {r[3]} | {r[4]:,} | {r[5]} | {r[6]} | {r[7]} | "
                f"+{r[7] - r[6]}" + (f" ({r[8].replace(' ', ', ')})" if r[8] else "") + " |")
mb = sum(r[6] for r in per_img) / len(per_img)
mn = sum(r[7] for r in per_img) / len(per_img)
head.append(f"| **Mean** | | | | | | **{mb:.1f}** | **{mn:.1f}** | +{mn - mb:.1f} |")
cnt = {}
for r in per_img:
    for s in r[8].split():
        cnt[s] = cnt.get(s, 0) + 1
head.append("\nSyscalls added to the profile without binding, by number of images: "
            + ", ".join(f"`{s}` ({n})" for s, n in sorted(cnt.items(), key=lambda x: (-x[1], x[0]))))
open(f"{HERE}/results/summary.md", "w").write("\n".join(head + md) + "\n")
with open(f"{HERE}/results/per_library.tsv", "w") as f:
    f.write("img\tlibrary\tsha256_16\tbinding_starts\tbinding_syscalls\tnobinding_starts\tnobinding_syscalls"
            "\tonly_without_binding\tonly_with_binding\n")
    f.write("".join("\t".join(map(str, r)) + "\n" for r in per_lib))
with open(f"{HERE}/results/per_image.tsv", "w") as f:
    f.write("img\tlibraries\tbinding_starts\tbinding_syscalls\tnobinding_starts\tnobinding_syscalls"
            "\tprofile_binding\tprofile_nobinding\tadded\n")
    f.write("".join("\t".join(map(str, r)) + "\n" for r in per_img))
print("\n".join(head))
