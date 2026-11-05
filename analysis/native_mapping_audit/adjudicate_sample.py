#!/usr/bin/env python3
"""
Record a verdict for each row of out/validation_sample_evidence.csv.

The rules below encode the decisions taken while reviewing the evidence by
hand (see RQ1_NATIVE_MAPPING.md, "Manual validation"). Rows whose evidence was
not decisive from the columns alone were checked directly against binaries and
JDK sources; those decisions are listed in MANUAL_DECISIONS with the evidence.

Verdicts:
  correct              target is the implementation of the declaration
  correct_partial      target implements one overload; other overloads of the
                       same name have targets that were not emitted
  incorrect_symbol     target implements a different signature / method
  incorrect_library    function is right but attributed to the wrong library
  misclassified        platform/intrinsic label is wrong
  approximate          no exact target exists; a related function was used

Writes out/validation_sample_adjudicated.csv and out/validation_summary.csv.
"""
import collections
import csv
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

MANUAL_DECISIONS = {
    # INTRINSIC stratum (JDK 8u JFR backport, Cassandra libjvm)
    "jdk.jfr.internal.JVM.getClassId": (
        "misclassified",
        "libjvm defines local jfr_class_id and the string 'getClassId'; it is JNI-registered, "
        "the extractor missed the row, so the whitelist label hid a real target"),
    "jdk.jfr.internal.JVM.setCompressedIntegers": (
        "misclassified",
        "no jfr_* target and no registration string in this libjvm; should be NOT_FOUND/dead, not intrinsic"),
    "jdk.jfr.internal.JVM.registerNatives": (
        "misclassified",
        "no Java_jdk_jfr_internal_JVM_registerNatives in this libjvm; should be NOT_FOUND/dead, not intrinsic"),
}


def verdict(r):
    descs = [d for d in r["java_native_descriptors"].split() if d.startswith("(")]
    multi = len(descs) > 1
    cat = r["stratum"]
    if r["method"] in MANUAL_DECISIONS:
        return MANUAL_DECISIONS[r["method"]]
    if cat == "platform":
        if r["jni_symbol_elsewhere"]:
            return ("misclassified",
                    "Linux library %s exports the exact Java_ symbol" % r["jni_symbol_elsewhere"])
        return ("correct", "non-Linux API (%s); exact Java_ symbol absent from every .so in the image"
                % r["et_symbol"])
    if cat == "manual_rule":
        if r["et_tag"] == "DIRECT_LIBC_BRIDGE":
            if r["et_symbol_in_lib"] == "yes":
                return ("correct", "JNA direct mapping to libc %s; symbol defined in %s"
                        % (r["et_symbol"], r["et_lib"]))
            return ("incorrect_library",
                    "JNA direct mapping to libc %s is right, but library recorded as %s which does not define it"
                    % (r["et_symbol"], r["et_lib"]))
        if r["et_tag"] == "SIGAR_LIST_BRIDGE":
            return ("approximate",
                    "libsigar exports no Java_ symbol for %s; mapped to list native %s that fills these objects"
                    % (r["method"], r["et_symbol"]))
        if r["et_tag"] == "JVM_BUILTIN":
            return ("correct", "JDK 8 Object.c/System.c registers %s" % r["et_symbol"])
    if r["et_symbol_in_lib"] == "no":
        return ("incorrect_library", "symbol not defined in %s" % r["et_lib"])
    if r["et_name_or_table_ok"] == "no":
        return ("incorrect_symbol", r["et_note"])
    if r["signature_match"] == "no":
        return ("incorrect_symbol",
                "chosen target's signature matches no Java declaration (%s); table: %s"
                % (" ".join(descs), r["table_rows"]))
    why = {"registered": "RegisterNatives row with matching signature recovered from %s" % r["et_lib"],
           "jni_static": "exact Java_ export in %s" % r["et_lib"],
           "jni_partial": "escaped/overloaded Java_ export in %s" % r["et_lib"],
           "netty_name": "netty_* registration function in %s, class and method tokens match" % r["et_lib"],
           }.get(cat, "evidence consistent")
    if r["lib_loaded_at_runtime"] == "no":
        why += "; library present in image but not opened during the startup trace"
    if multi and r["signature_match"] in ("yes",) and cat in ("registered", "jni_partial"):
        return ("correct_partial", why + "; %d overloads declared, one target emitted" % len(descs))
    return ("correct", why)


def main():
    with open(os.path.join(OUT, "validation_sample_evidence.csv")) as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["manual_verdict"], r["manual_evidence"] = verdict(r)
    with open(os.path.join(OUT, "validation_sample_adjudicated.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    verdicts = ["correct", "correct_partial", "approximate", "incorrect_symbol",
                "incorrect_library", "misclassified"]
    summ = collections.OrderedDict()
    for r in rows:
        s = summ.setdefault(r["stratum"], collections.Counter(population=int(r["stratum_population"])))
        s["sampled"] += 1
        s[r["manual_verdict"]] += 1
    with open(os.path.join(OUT, "validation_summary.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["stratum", "population", "sampled"] + verdicts)
        for k, s in summ.items():
            w.writerow([k, s["population"], s["sampled"]] + [s[v] for v in verdicts])
            print(k, dict(s))


if __name__ == "__main__":
    main()
