# SysJava artifact

SysJava builds a seccomp allowlist for a containerised Java application from
three parts: a capture of what the container loads, a bytecode analysis that
finds every Java-to-native binding (JNI, `RegisterNatives`, JNA, JNR-FFI, FFM),
and a call-graph analysis (SysPart) of the native code those bindings reach.
The tool is called EchoTrace in the code.

> **Status:** `1_latest_containers/` has its results. The result folders of
> `2_swat4j_vs_sysjava/` are placeholders until those runs finish.

## Layout

| Folder | Contents | Paper |
|---|---|---|
| [`1_latest_containers/`](1_latest_containers/README.md) | 10 newer-version images (JDK 8-25) | Table `tab:latest` |
| [`2_swat4j_vs_sysjava/`](2_swat4j_vs_sysjava/README.md) | SysJava vs SWAT4J on 10 JDK 8 images | Table `tab:results` |
| [`3_sysjava_vs_confine/`](3_sysjava_vs_confine/README.md) | SysJava vs Confine (to be added) | Table `tab:confine` |
| `Results/` | results of the original submission, unchanged | |
| [`docker_images/`](docker_images/README.md) | every image used, pinned by digest; Dockerfiles of the rebuilt JDK 8 images | |
| `echotrace/` | tool source (bytecode analysis), commit `52628c4` | |
| `echotrace_516fb46/` | the same tool one commit earlier; five latest-version results were made with it | |
| [`syspart/`](syspart/README.md) | how to build SysPart (third-party) | |
| [`swat4j/`](swat4j/README.md) | scripts that run SWAT4J unmodified | |
| `analysis/` | native-declaration coverage audit | |
| `tools/` | table builder, call-graph parser, and the scripts that assembled this folder | |
| `whitelist.sh` | rebuilds an allowlist without SysPart (B below) | |
| `setup.sh` | one-time setup for the full rerun (C below) | |

## Result folders

Each image has one folder (`results/<image>/` or `sysjava_results/<image>/`):

```
Binary_Analysis/syscalls_output_<image>/<image>.json   the seccomp profile
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
| B | bytecode analysis and native mapping on the shipped dataset; syscalls parsed from the shipped call graphs | JDK 17+, Maven, Python, binutils, xz | 5-15 min |
| C | the whole pipeline, including capture and SysPart | see below, root | 2-8 h |

### A. Tables from the shipped results

```bash
TABLE_ONLY=1 1_latest_containers/reproduce.sh
TABLE_ONLY=1 2_swat4j_vs_sysjava/reproduce.sh
```

### B. Allowlist without SysPart

```bash
./whitelist.sh zookeeper_3.9.5     # one image
./whitelist.sh all                 # every image with results
```

It unpacks the image's dataset, finds the native methods, maps them to start
functions, follows the shipped call graphs from those functions to the
syscalls, and builds the profile. Output in `<table>/whitelists_static/`:
`<image>.json`, and `<image>.diff.txt` against the shipped profile. Any start
function or library the shipped call graphs do not cover is listed in
`<image>.report.tsv`; that part needs C. On ZooKeeper and JRuby it gives the
same native methods and profile as the full run.

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
