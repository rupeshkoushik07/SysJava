# SysJava artifact

SysJava builds a seccomp allowlist for a containerised Java application from
three parts: a capture of what the container loads, a bytecode analysis that
finds every Java-to-native binding (JNI, `RegisterNatives`, JNA, JNR-FFI, FFM),
and a call-graph analysis (SysPart) of the native code those bindings reach.
The tool is called EchoTrace in the code.

> **Status:** `1_latest_containers/` and `2_swat4j_vs_sysjava/` have their final
> results; all twenty images pass under their generated profiles.

## Layout

| Folder | Contents | Paper |
|---|---|---|
| [`1_latest_containers/`](1_latest_containers/README.md) | 10 newer-version images (JDK 8-25) | Table `tab:latest` |
| [`2_swat4j_vs_sysjava/`](2_swat4j_vs_sysjava/README.md) | SysJava vs SWAT4J on 10 JDK 8 images | Table `tab:results` |
| [`3_sysjava_vs_confine/`](3_sysjava_vs_confine/README.md) | SysJava vs Confine (to be added) | Table `tab:confine` |
| `Results/` | results of the original submission, unchanged | |
| [`docker_images/`](docker_images/README.md) | every image used, pinned by digest; Dockerfiles of the rebuilt JDK 8 images | |
| `echotrace/` | tool source (bytecode analysis), commit `89bf135`; every result in both tables was made with it | |
| [`syspart/`](syspart/README.md) | how to build SysPart (third-party) | |
| [`swat4j/`](swat4j/README.md) | scripts that run SWAT4J unmodified | |
| `analysis/` | native-declaration coverage audit; binding-recovery ablation (`binding_ablation/`, RQ5); [`workload_validation/`](analysis/workload_validation/README.md) and [`workload_validation_latest/`](analysis/workload_validation_latest/README.md): the profiles of both tables under real workloads (base / log / enforce, every run's logs), and for the JDK 8 set a traced pass under Docker's default profile (sysdig; missing / performed / permitted syscalls and new binaries / libraries: the policy-validation table); `code_facts.md`: how binding recovery works, with pointers to the code | |
| `tools/` | call-graph parser (used by `generate_syscalls.py`) and the generators of Table III and tab:results | |
| `generate_syscalls.py` | generates an image's syscalls and profile from SysPart's shipped call graphs (B below) | |
| `setup.sh` | one-time setup for the full rerun (C below) | |

## Result folders

Each image has one folder (`results/<image>/` or `sysjava_results/<image>/`):

```
<image>.json                    the seccomp profile (also under Binary_Analysis/syscalls_output_<image>/)
Binary_Analysis/                SysPart results: callgraph.json.gz and syscalls.txt per library/executable
Bytecode_Analysis/              native_methods.txt and the JNI/JNA/JNR-FFI/FFM bindings
Dynamic_Analysis/               sysdig capture: what the container loaded and executed
dataset/                        the files copied out of the container (JARs, libraries, executables, JDK)
seccomp_runtime_test.log        the container restarted under its profile (PASS/FAIL)
pipeline_run.log                full log of the run
```

`dataset/` is an xz archive split into 45 MB parts:
`cat dataset/Dataset.tar.xz.part* | xz -dc | tar -x`.

Call graphs are gzipped (6.7 GB uncompressed, 1 GB compressed). Python reads
them directly with `json.load(gzip.open(path))`; `gunzip -k <file>` gives the
plain JSON.

## Reproducing the tables

| | Reruns | Needs | Per image |
|---|---|---|---|
| A | table rows from the shipped results | Python | seconds |
| B | bytecode analysis and native mapping on the shipped dataset; syscalls parsed from the shipped call graphs; the container run under the profile | JDK 17+, Maven, Python, binutils, xz; Docker for the container run | 5-15 min (Solr up to 80) |
| C | the whole pipeline, including capture and SysPart | see below, root | 2-8 h |

### A. Tables from the shipped results

```bash
TABLE_ONLY=1 1_latest_containers/reproduce.sh
TABLE_ONLY=1 2_swat4j_vs_sysjava/reproduce.sh
```

### B. Syscalls from SysPart's call graphs

```bash
python3 generate_syscalls.py zookeeper_3.9.5     # one image
python3 generate_syscalls.py all                 # every image with a shipped dataset
python3 generate_syscalls.py --no-run zookeeper_3.9.5   # without the container run (no Docker)
python3 generate_syscalls.py -q zookeeper_3.9.5         # one summary line per stage instead
```

It runs the pipeline's stages on the shipped capture and prints what the pipeline's run
prints (`results/<image>/pipeline_run.log`): the stage headers of the table's driver
(`scripts/run_latest_target.sh`, `scripts/run_jdk8_target.sh`), with the same numbers,
and the output of each tool as it runs. Stages 1-2 (start the container, sysdig capture)
are the shipped capture itself. Stage numbers below are the latest driver's; the JDK 8
driver numbers the merge 9 and the container run 10.

- **3.** unpacks the capture (JARs, native libraries, executables, Java runtime).
- **4.** bytecode analysis (`echotrace/`, the same JNADetector run as the pipeline):
  every native method and the JNI, JNA, JNR-FFI and FFM bindings.
- **5.** native mapping: each native method to the C function and library implementing
  it (the start functions).
- **6.** debug symbols are in the shipped capture already; adds the libraries the copied
  ones need and the SONAME links.
- **7-8.** SysPart: follows the shipped call graph of each library and executable
  (mapped libraries, executables, unanalysed loaded libraries, JNA/FFI-bound
  libraries) from those start functions to the reachable syscalls. This is the one
  stage whose output differs from the run's: it reads SysPart's call graphs instead of
  building them (`[n/40]` lines; `replay_syspart:` lines name start functions the
  call graph does not have, as in the original run). For the JDK 8 images it also adds
  the functions C++ libraries' vtables point to as start functions, and follows the
  call graphs of the libraries libjvm imports from (`extra_components/jvm_internal_imports`),
  as their pipeline does.
- **9.** named call graphs: functions and unnamed (fuzzyfunc) functions per call graph.
- **10.** builds the syscall sets (Java libraries, executables, runtime set, fallback
  libraries) and merges them into the seccomp profile; then prints the image's column
  of its table (Table III, or tab:results for a JDK 8 image).
- **11.** runs the container under the generated profile (`tools/check_profile.sh`):
  once without and once with the profile; PASS when it starts, keeps running for 60 s,
  answers its probe and logs no extra "Operation not permitted". Needs Docker (the
  image is pulled by digest from `docker_images/images.tsv`, or built for JDK 8);
  skipped without it.

Output in `<table>/generated_syscalls/<image>/`: the native methods and their
mapping, `syscalls.txt` for every library and executable, the four sets, the
profile `<image>.json`, `table_column.txt`, `seccomp_runtime_test.log` and
`diff.txt`, which compares the profile with the shipped one. Each tool's output is
also in its log in `work/static/<image>/`.

ZooKeeper 3.9.5 (8 minutes on the analysis host). The output has 37,950 lines, as
the run's `pipeline_run.log` does (37,948), almost all from the bytecode analysis;
below, each stage's first and last lines:

```
===== [2026-11-08 17:20:03] zookeeper_3.9.5 stage 3: extract JDK runtime, JARs, native libraries (from the shipped capture, 1_latest_containers/results/zookeeper_3.9.5/dataset/)
captured: 43 JARs, 74 native libraries, libjvm.so: 2

===== [2026-11-08 17:20:08] zookeeper_3.9.5 stage 4: bytecode analysis (JNADetector, code at 89bf135 in ~/SysJava/echotrace)
[JNADetector] target=~/SysJava/work/static/zookeeper_3.9.5/JARFILES_zookeeper_3.9.5
[JNADetector] out   =~/SysJava/work/static/zookeeper_3.9.5/outputs_zookeeper_3.9.5
[JNADetector] runtime=~/SysJava/work/static/zookeeper_3.9.5/RUNTIME_zookeeper_3.9.5
[JNADetector] work  =~/SysJava/work/static/zookeeper_3.9.5/outputs_zookeeper_3.9.5/jna_detector_work_20261108_172008
[JNADetector] wrote ~/SysJava/work/static/zookeeper_3.9.5/outputs_zookeeper_3.9.5/analyzed_jars.txt (target=43, runtime=50)
[JNADetector] detector.runtime.dir=~/SysJava/work/static/zookeeper_3.9.5/RUNTIME_zookeeper_3.9.5
[JNADetector] phase=dyn
[INFO] detector.runtime.dir jars: 50
[CTX] jars=43 (scan=43, cp=93) classes=6626 (scan=6626)
[CTX] resolved classes=6616 (scan=6616)
[CTX] body warm-up (parallel) done in 8s
[CTX] shared context ready in 11s
[DYN] classes=6616 out=~/SysJava/work/static/zookeeper_3.9.5/outputs_zookeeper_3.9.5/jna_detector_work_20261108_172008/dyn
[PASS 1] Populating summaries + field taints (fixed point, max 4 iterations)...
[PASS 1.0] strings=499 funcSummaries=0 nativeLibSummaries=0 fieldLibs=0 fieldFuncs=0
[PASS 1.1] strings=570 funcSummaries=0 nativeLibSummaries=0 fieldLibs=0 fieldFuncs=0
[... 37475 more lines ...]

Count of called native methods: 1286
 
Analysis results written to:
  - Native methods (1286): ~/SysJava/work/static/zookeeper_3.9.5/outputs_zookeeper_3.9.5/native_methods.txt
Time taken: 27.997 seconds
[JNADetector] done

===== [2026-11-08 17:22:47] zookeeper_3.9.5 stage 5: native mapping and start functions
============================================================
 Native mapping and start-function preparation
============================================================
LIB_DIRS:    ~/SysJava/work/static/zookeeper_3.9.5/LIBS_zookeeper_3.9.5
OUTPUTS_DIR: ~/SysJava/work/static/zookeeper_3.9.5/outputs_zookeeper_3.9.5
  1/3 Running mapped_updated.py
[... 124 more lines ...]
    Registered_:       974     (Registered_libjvm + JFR + Netty)
  Intrinsic (JIT):     0
Platform-excluded:    40
NOT_FOUND_IN_LIBS:    6

Output: ~/SysJava/work/static/zookeeper_3.9.5/outputs_zookeeper_3.9.5/mapped_method_syscalls.txt
  2/3 Filtering unresolved mappings
Filtering: ~/SysJava/work/static/zookeeper_3.9.5/outputs_zookeeper_3.9.5/mapped_method_syscalls.txt -> ~/SysJava/work/static/zookeeper_3.9.5/outputs_zookeeper_3.9.5/filtered_method_syscalls.txt
Wrote 2143 lines to ~/SysJava/work/static/zookeeper_3.9.5/outputs_zookeeper_3.9.5/filtered_method_syscalls.txt
  3/3 Writing per-library SysPart start files
Wrote combined: final.txt  (libs=24, methods=2102)
Wrote per-library files to: ~/SysJava/work/static/zookeeper_3.9.5/outputs_zookeeper_3.9.5
Native mapping preparation complete.
overloaded JNI methods detected: 6 (17 symbols); missing from mapping: 0; report: ~/SysJava/1_latest_containers/generated_syscalls/zookeeper_3.9.5/jni_overload_check.tsv

===== [2026-11-08 17:23:27] zookeeper_3.9.5 stage 6: debug symbols (in the shipped capture already); container dependencies and SONAME links
HAS_SYMTAB=53 NO_BUILD_ID=2 SYMBOLIZED=28 

===== [2026-11-08 17:23:27] zookeeper_3.9.5 stage 7-8: SysPart: mapped libraries, executed binaries, unanalysed loaded libraries and JNA/FFI bindings (call graphs of the shipped run, 1_latest_containers/results/zookeeper_3.9.5/Binary_Analysis/)
============================================================
 JNA / jnr-ffi / FFM binary analysis
============================================================
IMG_NAME: zookeeper_3.9.5
LIBS:     ~/SysJava/work/static/zookeeper_3.9.5/LIBS_zookeeper_3.9.5
reports:  ~/SysJava/work/static/zookeeper_3.9.5/outputs_zookeeper_3.9.5

Bindings: 6 symbols across 1 library
  util                     6 symbols

6 symbol(s) had an unresolved library and cannot be analysed:
  iface: 6

Resolving libraries against the mirror...
  util                     -> libutil.so.1

Wrote start-function files to ~/SysJava/work/static/zookeeper_3.9.5/jna_ffi_analysis/startfuncs
[... 52 more lines ...]
replay_syspart: 5 start function(s) not in the shipped call graph of libpcre.so.3; see ~/SysJava/work/static/zookeeper_3.9.5/syscalls_unanalysed_zookeeper_3.9.5/libpcre.so.3/replay_missing_starts.txt
[37/40] fallback library libpcre.so.3: 37 syscalls
replay_syspart: 19 start function(s) not in the shipped call graph of libpcre2-8.so.0; see ~/SysJava/work/static/zookeeper_3.9.5/syscalls_unanalysed_zookeeper_3.9.5/libpcre2-8.so.0/replay_missing_starts.txt
[38/40] fallback library libpcre2-8.so.0: 37 syscalls
replay_syspart: 17 start function(s) not in the shipped call graph of libselinux.so.1; see ~/SysJava/work/static/zookeeper_3.9.5/syscalls_unanalysed_zookeeper_3.9.5/libselinux.so.1/replay_missing_starts.txt
[39/40] fallback library libselinux.so.1: 74 syscalls
replay_syspart: 16 start function(s) not in the shipped call graph of libtinfo.so.6; see ~/SysJava/work/static/zookeeper_3.9.5/syscalls_unanalysed_zookeeper_3.9.5/libtinfo.so.6/replay_missing_starts.txt
[40/40] fallback library libtinfo.so.6: 47 syscalls
call-graph replay: no_callgraph_in_original=1, ok=40

===== [2026-11-08 17:25:33] zookeeper_3.9.5 stage 9: named call graphs: unnamed (fuzzyfunc) functions per result
libawt.so	functions=49760	fuzzy=0	syscalls=93
libawt_headless.so	functions=49854	fuzzy=0	syscalls=93
libawt_xawt.so	functions=56310	fuzzy=978	syscalls=109
libfontmanager.so	functions=52712	fuzzy=0	syscalls=93
[... 23 more lines ...]
sed	functions=4360	fuzzy=0	syscalls=73
uname	functions=3623	fuzzy=0	syscalls=39

===== [2026-11-08 17:25:33] zookeeper_3.9.5 stage 10: merge syscalls into seccomp profile, assemble results
╔══════════════════════════════════════════════════════════════╗
║              Syscall Merge & Analysis Tool                   ║
╚══════════════════════════════════════════════════════════════╝

IMG_NAME: zookeeper_3.9.5
Working directory: ~/SysJava/work/static/zookeeper_3.9.5

======================================================================
STEP 1: Processing Binary Syscalls
======================================================================

[Processing Binaries]
Directory: ~/SysJava/work/static/zookeeper_3.9.5/syscalls_BIN_zookeeper_3.9.5
Found 11 subdirectories

  ✓ bash: 89 syscalls
[... 125 more lines ...]
  - Added:       31 additional syscalls

Combined:
  - Total unique syscalls: 191
  - Includes: binaries + libraries + runc whitelist

Output files:
  - ~/SysJava/work/static/zookeeper_3.9.5/syscalls_BIN_zookeeper_3.9.5/binary_syscalls.txt (text)
  - ~/SysJava/work/static/zookeeper_3.9.5/syscalls_output_zookeeper_3.9.5/library_syscalls.txt (text)
  - ~/SysJava/work/static/zookeeper_3.9.5/syscalls_output_zookeeper_3.9.5/zookeeper_3.9.5.txt (text)
  - ~/SysJava/work/static/zookeeper_3.9.5/syscalls_output_zookeeper_3.9.5/zookeeper_3.9.5.json (seccomp profile)

⚠ Completed with warnings or errors
stage 10: merge reported items without results (listed above); profile written, continuing

===== [2026-11-08 17:25:33] zookeeper_3.9.5 stage results: the image's column of Table III (written to 1_latest_containers/generated_syscalls/zookeeper_3.9.5/table_column.txt)
      Native Method Resolution
      Native Methods                                1322
      SysJava Resolved                              1260
      Resolution Breakdown (SysJava)
        JNI Static (Java_*)                          650
        Partial (_1/$/__)                             15
        JNI Dynamic (RegisterNatives)                516
        JVM                                           46
        JFR/Netty                                     17
        JNA (Static / Dynamic)                     9 / 0
        FFI/FFM (incl. JNR-FFI)                        7
        Platform / Intrinsic / Dead                   62
        Not Found                                      0
      Syscall Allowlist (SysJava only)
      Java Lib Syscalls                              150
      Container Binary Syscalls                      113
      Unanalysed Lib Syscalls (Δ)                      3
      Go Whitelist (Δ)                                28
      Total Syscalls                                 191

===== [2026-11-08 17:25:34] zookeeper_3.9.5 stage 11: run the container under its profile
RESULT=PASS

===== [2026-11-08 17:27:40] zookeeper_3.9.5 stage done: finished in 8 min; profile: ~/SysJava/1_latest_containers/generated_syscalls/zookeeper_3.9.5/zookeeper_3.9.5.json
```

### C. Full rerun

Needs: Linux x86-64 with sudo, Docker 24+, sysdig 0.38+ (`--modern-bpf`),
JDK 17+, Maven, Python 3.10+, binutils, elfutils, `dpkg-deb`, SysPart
([`syspart/README.md`](syspart/README.md)), 8 cores, 64 GB RAM plus swap,
100 GB disk, network access.

```bash
SYSPART_ROOT=/path/to/SysPartCode ./setup.sh   # once
1_latest_containers/reproduce.sh               # tab:latest
2_swat4j_vs_sysjava/reproduce.sh               # tab:results (SysJava and SWAT4J)
```

Each script runs every tool its table compares and writes the table to
`<folder>/tables_rerun/`. Pass image names to run a subset; `STAGE=<n>`
resumes an image from stage *n*.

| Stage | Step |
|---|---|
| 1-3 | start the container, capture a clean start with sysdig, copy out what it loaded |
| 4 | bytecode analysis (native methods and bindings) |
| 5 | map native methods to native symbols (start functions) |
| 6 | restore debug symbols of stripped ELFs |
| 7-8 | SysPart on each mapped library, executable, unbound library and JNA/FFI entry point |
| 9-10 | merge everything with the runtime set into the profile |
| 11 | restart the container under the profile |

A rerun can differ where sysdig misses part of a start on a loaded host, or
where debug-symbol archives have changed. Images are pulled by digest.
