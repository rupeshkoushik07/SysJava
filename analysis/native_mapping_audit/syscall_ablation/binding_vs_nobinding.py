#!/usr/bin/env python3
"""
Binding vs. no binding, for one container (used for Tomcat 11.0.18 / JDK 25).

Per library, the binaries and the SysPart call graph are held fixed and only the
entry points change. Four arms:

  no_binding_exports  every function the .so exports (nm -D, type T/W/i): what a tool
                      without Java-to-native mapping has to assume Java may call
  no_binding_all      every function the library defines, exported or not (upper bound)
  sysjava, swat4j     the two mappings, taken from mechanism_ablation.py output
                      (per_library.csv), so the numbers match MAPPING_PER_LIBRARY.md

Libraries: every library mechanism_ablation.py analysed for the app (SysPart's
syscalls_output folders plus the jna_ffi_analysis libraries). A library SysPart has no
graph for (no binding found, e.g. libtcnative in Tomcat 11) reports 0 in every arm.

  binding_vs_nobinding.py --app tomcat_11.0.18 --mech out_mech_latest \
      --syspart <syscalls_output dir> --ffi <jna_ffi_analysis dir> \
      --libs <Dataset/LIBS_... dir> --out out_binding_tomcat11

Writes per_library.csv (counts and sets per library and mode), container.csv
(union over the libraries) and profile.csv (the whole deployed profile per arm: the
library union plus the --rest lists; SysJava's arm is checked against --profile).
"""
import argparse
import csv
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mechanism_ablation import Graph, lib_functions  # noqa: E402

ARMS = ["no_binding_exports", "no_binding_all", "sysjava", "swat4j"]


def exports(path):
    out = subprocess.run(["nm", "-D", "--defined-only", path], check=True,
                         capture_output=True, text=True).stdout
    names = set()
    for line in out.splitlines():
        p = line.split()
        if len(p) == 3 and p[1] in "TWi":
            names.add(p[2].split("@", 1)[0])
    return names


def find_binary(libs_dir, lib):
    for root, _, files in os.walk(libs_dir):
        if lib in files:
            return os.path.join(root, lib)
    sys.exit("binary %s not under %s" % (lib, libs_dir))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", required=True)
    ap.add_argument("--mech", required=True, help="mechanism_ablation.py output dir")
    ap.add_argument("--syspart", required=True, help="syscalls_output_<app> dir")
    ap.add_argument("--ffi", help="jna_ffi_analysis dir")
    ap.add_argument("--libs", required=True, help="dir holding the analysed .so files")
    ap.add_argument("--rest", nargs="*", default=[],
                    help="syscall lists the deployed profile adds regardless of mapping (binaries, "
                         "libraries without bindings, runtime whitelist)")
    ap.add_argument("--profile", help="recorded final profile (one syscall per line), as a check")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    mapped = {}
    with open(os.path.join(args.mech, "per_library.csv")) as f:
        for r in csv.DictReader(f):
            if r["app"] == args.app:
                mapped[(r["lib"], r["mode"])] = r
    dirs = {}
    for lib in sorted(os.listdir(args.syspart)):
        dirs[lib] = os.path.join(args.syspart, lib)
    if args.ffi:
        for lib in sorted(os.listdir(os.path.join(args.ffi, "libraries"))):
            dirs[lib] = os.path.join(args.ffi, "libraries", lib)

    rows = []
    union = {(arm, mode): set() for arm in ARMS for mode in ("full", "direct")}
    for lib in sorted({lib for lib, _ in mapped}):
        lib_dir = dirs[lib]
        g = Graph(lib_dir)
        # the library's own module only (SysJava's libssl starts include libcrypto symbols)
        funcs = lib_functions(lib_dir, lib)
        exp = exports(find_binary(args.libs, lib))
        starts = {
            "no_binding_exports": ["%s_%s" % (n, a) for n in sorted(exp & set(funcs)) for a in funcs[n]],
            "no_binding_all": ["%s_%s" % (n, a) for n in sorted(funcs) for a in funcs[n]],
        }
        for mode in ("full", "direct"):
            m = mapped[(lib, mode)]
            sets = {arm: set(g.reach(s, mode == "direct")) for arm, s in starts.items()}
            sets["sysjava"] = set(m["sysjava_set"].split())
            sets["swat4j"] = set(m["swat4j_set"].split())
            for arm in ARMS:
                union[(arm, mode)] |= sets[arm]
            nb = sets["no_binding_exports"]
            rows.append(dict(
                app=args.app, lib=lib, mode=mode,
                exported_functions=len(exp & set(funcs)), all_functions=len(funcs),
                sysjava_starts=m["sysjava_starts"], sysjava_mechanisms=m["sysjava_mechanisms"],
                swat4j_starts=m["swat4j_starts"],
                **{"%s_syscalls" % arm: len(sets[arm]) for arm in ARMS},
                nobinding_minus_sysjava=" ".join(sorted(nb - sets["sysjava"])),
                sysjava_minus_nobinding=" ".join(sorted(sets["sysjava"] - nb)),
                sysjava_minus_swat4j=" ".join(sorted(sets["sysjava"] - sets["swat4j"])),
                **{"%s_set" % arm: " ".join(sorted(sets[arm])) for arm in ARMS}))
            print("%-26s %-6s exports %5d all %6d | NB-exp %3d NB-all %3d SJ %3d SW %3d" % (
                lib[:26], mode, len(exp & set(funcs)), len(funcs), len(nb),
                len(sets["no_binding_all"]), len(sets["sysjava"]), len(sets["swat4j"])), flush=True)

    cont = []
    for mode in ("full", "direct"):
        u = {arm: union[(arm, mode)] for arm in ARMS}
        cont.append(dict(
            app=args.app, mode=mode, **{"%s_syscalls" % arm: len(u[arm]) for arm in ARMS},
            nobinding_minus_sysjava=" ".join(sorted(u["no_binding_exports"] - u["sysjava"])),
            sysjava_minus_nobinding=" ".join(sorted(u["sysjava"] - u["no_binding_exports"])),
            sysjava_minus_swat4j=" ".join(sorted(u["sysjava"] - u["swat4j"])),
            **{"%s_set" % arm: " ".join(sorted(u[arm])) for arm in ARMS}))

    # Whole deployed profile per arm (full mode, as SysJava's pipeline builds it):
    # the mapped-library union plus everything that does not depend on the mapping.
    def lines(path):
        with open(path) as f:
            return {l.strip() for l in f if l.strip()}
    rest = set().union(*(lines(p) for p in args.rest)) if args.rest else set()
    recorded = lines(args.profile) if args.profile else set()
    prof = {arm: rest | union[(arm, "full")] for arm in ARMS}
    profile = [dict(app=args.app, arm=arm, syscalls=len(prof[arm]),
                    vs_sysjava_added=" ".join(sorted(prof[arm] - prof["sysjava"])),
                    vs_sysjava_missing=" ".join(sorted(prof["sysjava"] - prof[arm])),
                    equals_recorded_profile=(prof[arm] == recorded) if args.profile else "",
                    set=" ".join(sorted(prof[arm]))) for arm in ARMS]
    for r in profile:
        print("profile %-20s %3d +[%s] -[%s] recorded=%s" % (
            r["arm"], r["syscalls"], r["vs_sysjava_added"], r["vs_sysjava_missing"], r["equals_recorded_profile"]))

    for name, data in (("per_library.csv", rows), ("container.csv", cont), ("profile.csv", profile)):
        with open(os.path.join(args.out, name), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0].keys()))
            w.writeheader()
            w.writerows(data)


if __name__ == "__main__":
    main()
