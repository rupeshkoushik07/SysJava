# Reproducing the native-mapping results (ICSE'27 major revision)

This folder answers the revision item *"define the resolution-rate denominator and manually
validate a stratified sample of additional mappings, reporting incorrect mappings"*, plus the
follow-up question of whether better mapping changes the syscall allowlist.

There are three analyses. Each has its own write-up:

| # | Question | Write-up | Main script |
|---|---|---|---|
| 1 | How many native methods does each tool map, and are SysJava's extra mappings correct? | [RQ1_NATIVE_MAPPING.md](RQ1_NATIVE_MAPPING.md) | `run_audit.sh` |
| 2 | Container level: does swapping SysJava's entry points for SWAT4J's change the app's syscall set? | [syscall_ablation/ENTRYPOINT_ABLATION.md](syscall_ablation/ENTRYPOINT_ABLATION.md) | `syscall_ablation/run_ablation.sh` |
| 3 | Library level, by binding mechanism (JNI, RegisterNatives, JVM_, JNA, FFM): which syscalls does SWAT4J's mapping miss, and why? | [syscall_ablation/MAPPING_PER_LIBRARY.md](syscall_ablation/MAPPING_PER_LIBRARY.md) | `syscall_ablation/run_mechanism_*.sh` |

Everything below can be rerun from scratch. Every run script was rerun once and its
outputs diffed against the previous run (identical).

---

## 0. Environment and ground rules

* Linux, Python 3.10+, standard library only (no pip packages). `nm` (binutils) is used by the audit.
* Paths assume the user's home layout. Override roots with environment variables:
  * `PROTOTYPE`: default `~/Prototype` (SysJava/EchoTrace results and `swat4j_mapping.py`)
  * `JDK8_RESULTS`: default `~/Tutorial/EchoTrace/Final_results_JDK8` (debug-symbol reruns)
* **SWAT4J is never modified.** We run `~/Prototype/swat4j_mapping.py`, a port of upstream
  SWAT4J's `binary_analyser.py`, as is. The only input we change is `--jdk-lib`. It points at
  the container's own JDK libraries, because the host JDK 8 that SWAT4J defaults to is no
  longer installed.
* **SysPart is never modified or rerun here.** All syscall numbers come from the call graphs
  SysPart already wrote (`callgraph.json`, `syscalls_with_callsites.txt`). Reachability is
  replayed with `~/Tutorial/EchoTrace/scripts/getsyscalls_lowmem.py`, or with an exact
  re-implementation of it in `mechanism_ablation.py`. Both are checked against SysPart's
  recorded `syscalls.txt` (see `check.csv` in each output folder).

## 1. Datasets

| Label used here | Image / version | JDK | Results folder (inputs) | SysPart graphs used | Debug symbols |
|---|---|---|---|---|---|
| zookeeper_3.4.14 | zookeeper 3.4.14 | 8 | `~/Prototype/Final_results_echotrace/zookeeper_3.4.14` | `$JDK8_RESULTS/zookeeper_3.4.14/Binary_Analysis_symbolized/` | yes |
| tomcat_7.0 | tomcat 7.0 | 8 | `.../Final_results_echotrace/tomcat_7.0` | `$JDK8_RESULTS/tomcat_7.0/Binary_Analysis_symbolized/` | yes |
| cassandra_3.0.29 | cassandra 3.0.29 | 8 | `.../Final_results_echotrace/cassandra_3.0.29` | `$JDK8_RESULTS/cassandra_3.0.29/Binary_Analysis_symbolized/` | yes |
| orientdb_3.2.19 | orientdb 3.2.19 | 8 | `.../Final_results_echotrace/orientdb_3.2.19` | `$JDK8_RESULTS/orientdb_3.2.19/Binary_Analysis_symbolized/` | yes |
| jruby_9.4.2.0 | jruby 9.4.2.0 | 8 | `.../Final_results_echotrace/jruby_9.4.2.0` | `$JDK8_RESULTS/jruby_9.4.2.0/Binary_Analysis_symbolized/` | yes |
| cassandra_5.0.6-bookworm | cassandra 5.0.6 | 17 | `.../Final_results_echotrace/cassandra_5.0.6-bookworm` | `$JDK8_RESULTS/cassandra_5.0.6-bookworm/Binary_Analysis_symbolized/` | yes |
| jetty_9.4.51-jdk8-buster | jetty 9.4.51 rebuilt on Debian 10 + Temurin 8 | 8 | `$JDK8_RESULTS/jetty_9.4.51-jdk8-buster` | same folder, `Binary_Analysis/` | yes |
| groovy_4.0.0-jdk8-buster | groovy 4.0.0 rebuilt | 8 | `$JDK8_RESULTS/groovy_4.0.0-jdk8-buster` | same folder, `Binary_Analysis/` | yes |
| solr_8.7.0-jdk8-buster | solr 8.7.0 rebuilt | 8 | `$JDK8_RESULTS/solr_8.7.0-jdk8-buster` | same folder, `Binary_Analysis/` | yes |
| tomcat_11.0.18 | tomcat 11.0.18 (temurin noble) | 25 | `~/Prototype/Final_results/tomcat_11.0.18-jdk25-temurin-noble` | same folder, `Binary_Analysis/` (+ `jna_ffi_analysis/`) | no |
| elasticsearch_7.1.0 | elasticsearch 7.1.0 | 12 | `~/Prototype/Final_results/elasticsearch_7.1.0` | same folder, `Binary_Analysis/` (+ `jna_ffi_analysis/`) | no |
| solr_slim | solr slim | 25 | `~/Prototype/Final_results/solr_slim` | same folder, `Binary_Analysis/` | no |
| groovy_latest | groovy latest | 21 | `~/Prototype/Final_results/groovy_latest` | same folder, `Binary_Analysis/` | no |
| zookeeper_latest | zookeeper latest | 17 | `~/Prototype/Final_results/zookeeper_latest` | same folder, `Binary_Analysis/` | no |

Not used, and why:

* **Elasticsearch 7.5.2 and Storm 2.4.0 JDK 8 rebuilds:** left out by decision (2026-11-05).
  The comparison already has enough containers, and Tomcat 11 is the worked example. To add
  them later: run `syscall_ablation/run_ablation_jdk8_rebuilds.sh <app>-jdk8-buster`, then add
  the app to `run_mechanism_ablation.sh`.
* **cassandra_latest:** SysPart only analysed `libawt.so`, so the run is incomplete.
* **jetty_latest:** its libjvm call graph is truncated (O11). It is audited (`out_latest/`) but
  left out of the syscall comparison.
* **jruby_latest:** its 39 JNR-FFI bindings were detected but never run through SysPart (no
  `jna_ffi_analysis/`), and its bytecode output is split across two folders.
* The 10-image latest-versions rerun (`~/Tutorial/EchoTrace_latest`) is in progress in another
  session. Use it when finished; same scripts, new `--app` paths.

## 2. Analysis 1: mapping audit (denominator, coverage, validation)

```bash
cd ~/Tutorial/rq1_native_mapping
./run_audit.sh                    # 10 JDK 8 apps -> out/
./run_audit_mechanism_sets.sh     # Groovy+Solr JDK8 rebuilds -> out_jdk8_gs/, Tomcat 11 -> out_tomcat11/, newer containers -> out_latest/
```

Two more audits are produced by the ablation scripts in section 3: Cassandra 5 → `out_c5/`,
Jetty JDK 8 rebuild → `out_jdk8/`.

What each audit writes (`<out>/`):

* `per_app_summary.csv`: denominator (distinct `class.method` native names), mapped and
  accounted counts for each tool. **This is the source of the coverage tables.**
* `per_method.csv`: one row per native method, with both tools' symbol, library, tag and
  automatic checks. **Input to analyses 2 and 3.**
* `auto_check_failures.csv`, `validation_sample.csv`: automatic consistency checks, and the
  stratified sample (seed 20261104).
* `run_audit.sh` additionally runs `collect_sample_evidence.py` → `overload_check.csv`,
  `overload_mismatches.csv`, `validation_sample_evidence.csv`; `platform_check.py` →
  `platform_exclusion_errors.csv`; and `adjudicate_sample.py` →
  `validation_sample_adjudicated.csv`, `validation_summary.csv`.

SWAT4J outputs (unmodified tool):

* `swat4j_rerun_orientdb/`
* `syscall_ablation/swat4j_jdk8/<app>/`
* `syscall_ablation/swat4j_latest/<app>/`

Each has a `run.log` and `swat4j_summary.txt`.

## 3. Analysis 2: container-level entry-point swap

```bash
cd ~/Tutorial/rq1_native_mapping/syscall_ablation
./run_ablation.sh                                       # 5 audit apps -> out/, Cassandra 5 -> out_c5/
./run_ablation_jdk8_rebuilds.sh jetty_9.4.51-jdk8-buster   # -> ../out_jdk8 (audit), out_jdk8/ (ablation)
```

Outputs: `per_app.csv` (app union for each arm), `per_library.csv`, `sysjava_only.csv` (the call
path for every syscall SWAT4J's mapping misses), `check.csv` (replay == recorded), and `logs/`.

## 4. Analysis 3: per library, per binding mechanism

```bash
cd ~/Tutorial/rq1_native_mapping/syscall_ablation
./run_mechanism_ablation.sh   # older apps (mostly JDK 8)  -> out_mech/
./run_mechanism_latest.sh     # newer containers (JDK 12-25) -> out_mech_latest/
python3 summarize_mechanisms.py \
  --set older=out_mech newer=out_mech_latest \
  --audit ../out/per_app_summary.csv ../out_c5/per_app_summary.csv ../out_jdk8/per_app_summary.csv \
          ../out_jdk8_gs/per_app_summary.csv ../out_tomcat11/per_app_summary.csv ../out_latest/per_app_summary.csv
                              # -> out_mech_summary/
```

Prerequisites: the audits from section 2 and section 3 (`../out*/per_method.csv`).

`mechanism_ablation.py` outputs (`out_mech*/`):

* `per_library.csv`: one row per (app, library, mode). Columns:
  * entry points per SysJava mechanism, and SWAT4J's entry points;
  * syscall counts and full syscall sets for both arms;
  * `missed` (SysJava minus SWAT4J) and `swat4j_only`.
* `mechanisms.csv`: one row per (app, library, mode, mechanism). Gives the syscalls reached
  from that mechanism's entry points alone, and how many of them SWAT4J's entry points do not
  reach.
* `missed.csv`: for each syscall SWAT4J's mapping misses, the mechanism(s) that reach it, an
  example entry point and its Java method.
* `check.csv`: full-mode replay of SysJava's entry points equals SysPart's `syscalls.txt`. It
  must be all `True`.

`summarize_mechanisms.py` outputs (`out_mech_summary/`):

* `per_container.csv`: per-container table.
* `per_mechanism.csv`: per-mechanism table.
* `differing.csv`: every library whose syscalls differ.
* `excluded.csv`: known SysJava false positives, kept out of totals.

Case-study paths:

```bash
python3 trace_path.py <syspart_lib_dir> <entry_function> <syscall> [--direct]
# e.g. Tomcat 11 FFM:
python3 trace_path.py ~/Prototype/Final_results/tomcat_11.0.18-jdk25-temurin-noble/Binary_Analysis/jna_ffi_analysis/libraries/libssl.so.3 SSL_do_handshake arch_prctl --direct
```

### Method details that affect the numbers

* **Two reachability modes.**
  * `full` is SysPart's model: an indirect call goes to every address-taken function.
  * `direct` drops `INDIRECT` edges but keeps `DIRECT`, `INDIRECT_RESOLVED` and syscall edges.
    It is not sound. It exists to remove the address-taken blow-up, so each mechanism's own
    contribution becomes visible.
* **Mechanism of a SysJava entry point.** It is the audit tag of the method that produced it:
  * JNI → JNI static
  * JNI_DYNAMIC and NETTY → RegisterNatives app
  * REGISTERED → RegisterNatives JVM
  * JVM and JVM_BUILTIN → JVM_ entry
  * DIRECT_LIBC_BRIDGE → JNA (all such rows are JNA direct-mapped classes)
  * SIGAR_LIST_BRIDGE → manual bridge

  JNA, JNR-FFI and FFM entry points in `jna_ffi_analysis/` take their mechanism from the
  `source_report` column of `resolved_bindings.tsv`.
* **SWAT4J entry points for a library:** every symbol SWAT4J mapped (Java_XXX or JVM_XXX) that
  the analysed library defines, *whatever file SWAT4J named*. This is deliberately generous to
  SWAT4J; see observations O3 and O4.
* **The library's own functions:** those in the module named like the SysPart folder, plus the
  module that defines SysPart's start functions (see O4).

## 4b. Analysis 4: Tomcat 11, no binding vs. SysJava vs. SWAT4J

Write-up: [syscall_ablation/TOMCAT11_BINDING.md](syscall_ablation/TOMCAT11_BINDING.md).

```bash
cd ~/Tutorial/rq1_native_mapping/syscall_ablation
./run_mechanism_latest.sh      # prerequisite: out_mech_latest/ (SysJava and SWAT4J sets)
./run_binding_tomcat11.sh      # -> out_binding_tomcat11/{per_library,container,profile}.csv
```

* **No binding** means every exported function (`nm -D --defined-only`, types T/W/i) of the
  library's own module is an entry point. `no_binding_all` uses every function of the module
  (upper bound).
* Binaries come from `~/Prototype/Final_results/tomcat_11.0.18-jdk25-temurin-noble/Dataset/LIBS_*`.
  Their md5 matches the copies SysPart analysed.
* The module is restricted to the library itself. SysJava's libssl FFM start list includes
  libcrypto symbols; counting those would inflate libssl's no-binding set.
* libtcnative has an empty SysPart graph (no binding found), so the no-binding arm is not
  measured for it.
* Check: `profile.csv` row `sysjava` has `equals_recorded_profile=True` (166 syscalls).

## 4c. Analysis 5: Tomcat 11.0.22, debug-symbol graphs (in progress)

The graphs are built by another session: `~/Tutorial/EchoTrace/ablation/run_ablation.sh`, variant
G, output `~/Tutorial/EchoTrace/ablation/tomcat_11.0.22/`. Its arms are A (every function) and
B (SysJava binding). This analysis only reads that folder and adds two arms over the same
graphs, using the same reachability rules (`lean_syscalls.py`):
E, every exported function; and S, SWAT4J's mapping.

```bash
cd ~/Tutorial/rq1_native_mapping/syscall_ablation
./run_binding_tomcat11_0_22.sh   # -> out_binding_tomcat11_0_22/{per_library,container,pending}.csv, starts/<arm>/<lib>.txt (start-function names), why.csv (start functions behind each differing syscall)
```

* **SWAT4J:** `swat4j_mapping.py`, unmodified, run on
  `EchoTrace_latest/workspaces/tomcat_11.0.22/outputs_tomcat_11.0.22/native_methods.txt` with
  `--libs-dir Final_results_latest_versions/tomcat_11.0.22/Dataset/LIBS_tomcat_11.0.22` and
  `--jdk-lib .../JDK25_LIBS`. Result: 199/269 (175 `Java_XXX`, 24 `JVM_XXX`), including all 92
  tcnative methods. Output: `swat4j_latest/tomcat_11.0.22/`.
* **Check:** `check_A_equals_ablation` and `check_B_equals_ablation` must be True, meaning our
  recomputation equals the ablation's own `syscalls.txt`.
* **Pending libraries:** a library whose ablation graph is not finished is listed in
  `pending.csv`. Rerun the script once it finishes.
* **Run of 2026-11-05 (ablation finished; 12.5 min):** libjvm stays pending, because its
  no-binding graph never finished (`A/libjvm.so/DID_NOT_FINISH`, bad_alloc at 35 and 60 GB).
  `check_A` is True for all six libraries. `check_B` is True only for libtcnative and libzip;
  see O13. Union over the six libraries, all arms walked on the A graph: A 127, E 127,
  B 119, S 116.
  * E minus B: chmod fsync getppid mlock mlock2 rename statfs utimensat.
  * B minus S: accept listen sendmsg. This is an artifact of the A graph (O13). On the
    ablation's own B graphs, SWAT4J's start functions equal SysJava's in libtcnative, libjava,
    libnet and libzip (same names), and those four already reach all 44 libssl/libcrypto
    syscalls. So over the six libraries the SWAT4J union equals the SysJava union (116, same
    set).
* **Deployed-profile check:** not yet. It needs stage 10 of the pipeline, which fills
  `Final_results_latest_versions/tomcat_11.0.22/` with the BIN, unanalysed and final-profile
  files. Then pass `--rest` and `--profile` as in 4b.

## 5. Observations log (things that bit us, and how they were handled)

* **O1. Table I in the submission is not reproducible as printed.** Jetty 225 and Tomcat 614
  are category sums, and the SWAT4J row is our own rerun, not published numbers. See
  RQ1_NATIVE_MAPPING.md.
* **O2. `Final_results_echotrace` mixes JDKs.** Some of its images are JDK 11/13/17. Analyses 2
  and 3 use the debug-symbol JDK 8 rebuilds wherever they exist.
* **O3. Duplicate library copies.** JNI libraries are often extracted twice: once from the jar,
  and once into a temp copy that the running JVM loads (e.g. OrientDB `liblz4-java-2525….so` and
  `liblz4-java-8074….so`, byte-identical). SWAT4J names one copy, SysPart may analyse the other.
  A file-name join wrongly gave SWAT4J zero entry points, so we credit SWAT4J by symbol name.
* **O4. SysPart folder name ≠ analysed module.** The folder `libzstd-jni-1.5.7-2.so` (Cassandra 5)
  contains the graph of module `libzstd-jni-1.5.7-2_zstd-jni-1.5.7-2.so`. A filter on folder name
  found no functions, so SWAT4J's symbols looked unresolvable. Fixed by also accepting the module
  that defines SysPart's start functions.
* **O5. JDK 8 legacy `Unsafe` overloads** (`Unsafe_GetByte140`, …) are RegisterNatives targets
  that the audit records under other names (the 62 wrong overloads in RQ1_NATIVE_MAPPING.md).
  They are classified as RegisterNatives JVM by name.
* **O6. SysJava false positive (excluded).** Groovy 4.0.0's FFM hit `VerifyClass` → `libverify.so`.
  The detector read Groovy's Ant task `org.codehaus.groovy.ant.VerifyClass` as a downcall. It is
  listed in `excluded.csv` and kept out of the totals.
* **O7. SysJava gap (reported, not fixed).** Elasticsearch 7.1.0's `SystemCallFilter` binds libc
  `prctl` and `syscall` through a JNA interface. The detector found both, but recorded the library
  as `<?>` in `jna_hits.txt`, so `jna_ffi_analysis` left them unresolved (`unresolved_bindings.tsv`).
  `prctl` and `seccomp` are still in the final profile, through other paths.
* **O8. The FFM path in Tomcat 11 is exercised at runtime.** The sysdig capture shows the `java`
  process opening `/lib/x86_64-linux-gnu/libssl.so.3` and `libcrypto.so.3`
  (`Dynamic_Analysis/sysdig_outputs_*/libs_by_pid.txt`).
* **O9. Shell pitfall.** In `(cd .. && cmd $PWD/x)`, `$PWD` expands *after* the `cd`. An early
  audit therefore read a non-existent SWAT4J folder and silently reported `sw_mapped=0`. The run
  scripts now use absolute paths fixed before any `cd`. Sanity check: `sw_mapped` in
  `per_app_summary.csv` must match `MAPPED:` in that app's `swat4j_summary.txt`.
* **O11. Broken SysPart outputs in older `~/Prototype/Final_results` runs (not debug-symbol reruns).**
  Each affects both arms equally, so the comparison stays fair:
  * `jetty_latest/.../libjvm.so/callgraph.json` holds 17,302 functions, but `allfunctions.txt`
    lists 52,878 for libjvm. Its libjvm then reaches only 14 syscalls and libjava only 20, so
    **jetty_latest is excluded** from the newer set.
  * `solr_slim/.../libsnappyjava_snappy-java-1.1.10.8.so` has no `startfuncs_with_addr.txt`.
  * `groovy_latest/.../libawt.so/callgraph.json` is cut off mid-file (invalid JSON at
    24,449,671 bytes).

  The last two are skipped and listed in `out_mech_latest/skipped.csv`.
* **O12. Library union is not the deployed profile.** `mechanism_ablation.py` compares the
  union of the analysed native libraries. The deployed profile also adds `syscalls_BIN_*`,
  `syscalls_unanalysed_*` and `~/Prototype/Final_results_echotrace/dockerd_containerd_syscall.txt`
  (117 syscalls), so many library-level misses come back through those parts:
  * Tomcat 11's `arch_prctl` is in the Docker whitelist (`out_binding_tomcat11/profile.csv`:
    SWAT4J 166 = SysJava 166 = recorded).
  * Elasticsearch 7.1.0 keeps all but `mlockall`.
  * Cassandra 3.0.29 keeps all but `mlockall` and `munlockall`.

  The ES and Cassandra results come from a manual `grep -cx` over those three lists, not yet
  scripted.
* **O13. A SysPart `-a 23` graph depends on its roots.** The same start functions reach
  fewer syscalls on a graph rooted only at them than on the graph rooted at every function,
  because indirect-call targets are resolved over the code the roots reach. On the
  ablation's own binding-only graphs (B), with the same 75/107 starts:
  * libssl reaches 44 syscalls there, but 59 on the all-function graph (A);
  * libcrypto reaches 44 there, but 62 on A.
  For libjava and libnet the pipeline's own binding-rooted runs give 107/104, against 109/107
  on A. So arms E (exports) and S (SWAT4J) walked on the A graph are over-estimates. A fair E
  and S needs its own SysPart run per library. The fair binding numbers are the ablation's
  own B (`summary.md`, regenerated 2026-11-05 without libjvm): over the same six libraries as
  `out_binding_tomcat11_0_22/`, 357 start functions reach 116 syscalls with binding, and 12,914
  reach 127 without.
* **O10. Load.** The host is shared, and each libjvm graph takes several GB to load. Run at most
  two `mechanism_ablation.py` processes at once.
