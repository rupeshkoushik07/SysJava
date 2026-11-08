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
| `analysis/` | native-declaration coverage audit; binding-recovery ablation (`binding_ablation/`, RQ5); `code_facts.md`: how binding recovery works, with pointers to the code | |
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
| B | bytecode analysis and native mapping on the shipped dataset; syscalls parsed from the shipped call graphs; the container run under the profile | JDK 17+, Maven, Python, binutils, xz; Docker for step 7 | 5-15 min (Solr up to 80) |
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
python3 generate_syscalls.py --no-run zookeeper_3.9.5   # steps 1-6 only (no Docker)
python3 generate_syscalls.py -v zookeeper_3.9.5         # print every line of every tool
```

For the image it:
1. unpacks the dataset (JARs, native libraries, executables, Java runtime);
2. runs the bytecode analysis: every native method and the JNI, JNA, JNR-FFI and FFM bindings;
3. maps each native method to the C function and library implementing it (the start functions);
4. follows SysPart's shipped call graph of each library and executable from those
   start functions to the reachable syscalls;
5. builds the syscall sets (Java libraries, executables, runtime set, fallback
   libraries) and merges them into the seccomp profile;
6. prints the results as the image's column of its table (Table III, or tab:results
   for a JDK 8 image): native methods by
   mapping kind (JNI static, partial, JNI dynamic, JVM, JFR/Netty, JNA, FFI/FFM,
   platform/intrinsic, not found) and the syscall rows (Java libraries, container
   executables, unanalysed libraries, runtime whitelist, total);
7. runs the container under the generated profile, as the pipeline's last stage
   (`tools/check_profile.sh`): once without and once with the profile; PASS when it
   starts, keeps running for 60 s, answers its probe and logs no extra "Operation not
   permitted". Needs Docker (the image is pulled by digest from
   `docker_images/images.tsv`, or built for JDK 8); skipped without it.

Output in `<table>/generated_syscalls/<image>/`: the native methods and their
mapping, `syscalls.txt` for every library and executable, the four sets, the
profile `<image>.json`, `table_column.txt` (step 6), `seccomp_runtime_test.log`
(step 7) and `diff.txt`, which compares the profile with the shipped one. Logs are
in `work/static/<image>/`. While it runs, it prints each tool's main lines with the
time (every line with `-v`).

ZooKeeper 3.9.5, as printed (8 minutes on the analysis host). The timed lines are
the progress of each tool as it runs; the untimed lines under them are the step's result:

```
[16:10:55] zookeeper_3.9.5 1. unpack the dataset (2 parts)
      43 JARs, 74 libraries, 12 executables
[16:11:00] zookeeper_3.9.5 2. bytecode analysis (echotrace, commit 89bf135)
      16:11:00 > JNADetector on the JARs, one pass per kind of binding, then the native methods (log: work/static/zookeeper_3.9.5/bytecode.log)
      16:11:00   pass 1/6: dynamic JNA calls (Function.getFunction)
      16:11:12     classes loaded in 11s
      16:11:16     dynamic-JNA hits: 0
      16:11:16   pass 2/6: JNA interfaces (Native.load)
      16:11:37     classes loaded in 20s
      16:11:37     7 Native.load calls
      16:11:40     JNA interface hits: 29
      16:11:40   pass 3/6: JNA direct mapping (Native.register)
      16:11:58     classes loaded in 18s
      16:12:00     JNA direct-mapped hits: 0
      16:12:00   pass 4/6: FFM downcalls (Linker)
      16:12:20     classes loaded in 20s
      16:12:23     FFI hits: 7
      16:12:23   pass 5/6: JNR-FFI interfaces
      16:13:17     jnr-ffi hits: 0
      16:13:17   pass 6/6: native methods reachable in the call graph (RTA)
      16:13:17     6640 classes
      16:13:17     following the calls from every method
      16:13:37     30012 native calls so far
      16:13:45     77597 methods visited
      16:13:45     1286 native methods called
      1286 native methods; 36 JNA, 0 JNR-FFI, 7 FFM bindings
[16:13:46] zookeeper_3.9.5 3. map native methods to C functions (start functions per library)
      16:13:46 > scripts/prepare_native_mapping.sh: JNI symbols and RegisterNatives tables of the libraries (log: work/static/zookeeper_3.9.5/mapping.log)
      16:13:46   1/3 Running mapped_updated.py
      16:13:47       1404 Java_ symbols in the libraries
      16:13:49       890 RegisterNatives bindings in the libraries
      16:14:19       860 RegisterNatives entries of libjvm, libjava and Netty
      16:14:20       classifying 1286 native methods
      16:14:25       resolved 1240 (96%)
      16:14:25       not in the libraries: 6
      16:14:25   2/3 Filtering unresolved mappings
      16:14:25   3/3 Writing per-library SysPart start files
      16:14:25       start functions: 2102 in 24 libraries
      16:14:25 > scripts/relink_sonames.sh (log: work/static/zookeeper_3.9.5/relink.log)
      16:14:25   SONAME links: 0 created, 6 present
      16:14:25 > scripts/analyse_jna_ffi.py: JNA, JNR-FFI and FFM symbols to their libraries (log: work/static/zookeeper_3.9.5/jna_ffi.log)
      16:14:25   6 symbols across 1 library
      16:14:25   6 symbols without a library to analyse
      16:14:26   util -> libutil.so.1
      16:14:26 > manual mappings: 1 start functions added
      2099 native methods mapped (JNI 1088, JNI_DYNAMIC 880, REGISTERED 73, JVM 41, NETTY 17); 24 libraries with start functions; 1 manual mappings added
[16:14:26] zookeeper_3.9.5 4. syscalls from SysPart's shipped call graphs
      16:14:26 > tools/whitelist_from_callgraphs.py: each call graph from its start functions (log: work/static/zookeeper_3.9.5/callgraphs.log)
      16:14:26   [1/40] JNA/FFI library libutil.so.1: 38 syscalls
      16:14:26   [2/40] executable bash: 89 syscalls
      16:14:26   [3/40] executable chown: 53 syscalls
      16:14:26   [4/40] executable dirname: 38 syscalls
      16:14:26   [5/40] executable env: 40 syscalls
      16:14:26   [6/40] executable grep: 43 syscalls
      16:14:26   [7/40] executable id: 56 syscalls
      16:14:27   [8/40] executable java: 66 syscalls
      16:14:27   [9/40] executable ls: 55 syscalls
      16:14:27   [10/40] executable sed: 73 syscalls
      16:14:27   [11/40] executable uname: 39 syscalls
      16:14:36   [12/40] library libawt.so: 93 syscalls
      16:14:44   [13/40] library libawt_headless.so: 93 syscalls
      16:14:54   [14/40] library libawt_xawt.so: 109 syscalls
      16:15:02   [15/40] library libfontmanager.so: 93 syscalls
      16:15:02   [16/40] library libj2gss.so: 37 syscalls
      16:15:10   [17/40] library libjava.so: 109 syscalls
      16:15:19   [18/40] library libjavajpeg.so: 93 syscalls
      16:15:19   [19/40] library libjlinenative.so: 38 syscalls
      16:15:27   [20/40] library libjvm.so: 93 syscalls
      16:15:35   [21/40] library liblcms.so: 93 syscalls
      16:15:43   [22/40] library libmanagement.so: 93 syscalls
      16:15:51   [23/40] library libnet.so: 98 syscalls
      16:15:51   [24/40] library libnetty_tcnative-@VERSION@.so: 44 syscalls
      16:15:51   [25/40] library libnetty_tcnative_linux_x86_64.so: 44 syscalls
      16:15:51   [26/40] library libnetty_transport_native_epoll_x86_64-4.1.130.Final.so: 67 syscalls
      16:15:51   [27/40] library libnetty_transport_native_epoll_x86_64.so: 67 syscalls
      16:15:59   [28/40] library libnio.so: 118 syscalls
      16:15:59   [29/40] library libsnappyjava.so: 37 syscalls
      16:16:07   [30/40] library libzip.so: 93 syscalls
      16:16:07   [31/40] fallback library libacl.so.1: 56 syscalls
      16:16:15   [32/40] fallback library libextnet.so: 94 syscalls
      16:16:23   [33/40] fallback library libjimage.so: 93 syscalls
      16:16:23   [34/40] fallback library libjli.so: 66 syscalls
      16:16:23   [35/40] fallback library libjsvml.so: 37 syscalls
      16:16:31   [36/40] fallback library libmanagement_ext.so: 93 syscalls
      16:16:31   [37/40] fallback library libpcre.so.3: 37 syscalls
      16:16:31   [38/40] fallback library libpcre2-8.so.0: 37 syscalls
      16:16:31   [39/40] fallback library libselinux.so.1: 74 syscalls
      16:16:31   [40/40] fallback library libtinfo.so.6: 47 syscalls
      40 call graphs parsed; 1 library/executable without a call graph in the original run either (kept as shipped)
[16:16:31] zookeeper_3.9.5 5. syscall sets and seccomp profile
      16:16:31 > scripts/merge_all_syscalls.py (log: work/static/zookeeper_3.9.5/merge.log)
      16:16:31   Processing Binary Syscalls
      16:16:31   Processing Library Syscalls
      16:16:31   Processing Unanalysed Dynamically Loaded Libraries
      16:16:31   Loading JNA/FFI Reachable Syscalls
      16:16:31   Loading runc.txt Default Whitelist
      16:16:31   Creating Combined Syscalls File
      16:16:31   Generating Seccomp Profile
      Java libraries 150, executables 113, runtime set +28, fallback libraries +3; profile 191
[16:16:31] zookeeper_3.9.5 6. results (the image's column of Table III)
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
[16:16:33] zookeeper_3.9.5 7. run the container under the profile
      16:16:33 > tools/check_profile.sh: the container once without and once with the profile (log: 1_latest_containers/generated_syscalls/zookeeper_3.9.5/seccomp_runtime_test.log)
      16:16:34   baseline (no profile)
      16:16:36   baseline_ready_after=2s
      16:17:36   baseline_state=running exit=0
      16:17:36   baseline_probe=ok tcp_2181
      16:17:36   baseline_eperm_lines=0
      16:17:36   with seccomp profile
      16:17:38   ready_after=3s
      16:18:38   state_after_60s=running exit=0
      16:18:38   probe=ok tcp_2181
      16:18:38   eperm_lines=0 (baseline 0)
      without profile: ready after 2s, running exit=0, probe ok tcp_2181
      with profile (191 syscalls): ready after 3s, running exit=0 after 60 s, probe ok tcp_2181, EPERM lines 0 (baseline 0)
      RESULT=PASS  (log: 1_latest_containers/generated_syscalls/zookeeper_3.9.5/seccomp_runtime_test.log)
Done in 8 min. Profile: 1_latest_containers/generated_syscalls/zookeeper_3.9.5/zookeeper_3.9.5.json; all outputs in 1_latest_containers/generated_syscalls/zookeeper_3.9.5/
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
