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
in `work/static/<image>/`.

ZooKeeper 3.9.5, as printed (8 minutes on the analysis host):

```
[13:38:04] zookeeper_3.9.5 1. unpack the dataset (2 parts)
      43 JARs, 74 libraries, 12 executables
[13:38:10] zookeeper_3.9.5 2. bytecode analysis (echotrace, commit 89bf135)
      1286 native methods; 36 JNA, 0 JNR-FFI, 7 FFM bindings
[13:41:03] zookeeper_3.9.5 3. map native methods to C functions (start functions per library)
      2099 native methods mapped (JNI 1088, JNI_DYNAMIC 880, REGISTERED 73, JVM 41, NETTY 17); 24 libraries with start functions; 1 manual mappings added
[13:41:44] zookeeper_3.9.5 4. syscalls from SysPart's shipped call graphs
      40 call graphs parsed; 1 library/executable without a call graph in the original run either (kept as shipped)
[13:43:50] zookeeper_3.9.5 5. syscall sets and seccomp profile
      Java libraries 150, executables 113, runtime set +28, fallback libraries +3; profile 191
[13:43:51] zookeeper_3.9.5 6. results (the image's column of Table III)
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
[13:43:52] zookeeper_3.9.5 7. run the container under the profile
      without profile: ready after 2s, running exit=0, probe ok tcp_2181
      with profile (191 syscalls): ready after 2s, running exit=0 after 60 s, probe ok tcp_2181, EPERM lines 0 (baseline 0)
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
