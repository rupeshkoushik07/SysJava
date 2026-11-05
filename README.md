# SysJava artifact

SysJava builds a seccomp allowlist for a containerised Java application. It
combines a dynamic capture of what the container loads (JARs, native libraries,
executables), a bytecode analysis that finds every Java-to-native binding (JNI
static and `RegisterNatives`, JNA, JNR-FFI, FFM), and a binary call-graph
analysis (SysPart) of the native code those bindings reach. The tool is called
EchoTrace in the code.

This artifact contains the tool source, the scripts that run the whole pipeline
for each container, the Docker images used (pinned by digest), and scripts that
rebuild the tables from the results.

> **Status:** the results of the ten latest-version images (`1_latest_containers/results/`)
> are included. The result folders of `2_swat4j_vs_sysjava/` are placeholders
> (`PENDING.md`) while those final runs finish.

## Layout

| Folder | What it holds | Paper |
|---|---|---|
| [`1_latest_containers/`](1_latest_containers/README.md) | Results for the 10 newer-version images (JDK 8-25): Cassandra 5.0.8, ZooKeeper 3.9.5, Tomcat 11.0.22, Solr 10.0.0, Groovy 5.0.6, OrientDB 3.2.53, Jetty 12.1.10, Elasticsearch 7.1.0, Storm 2.8.8, JRuby 10.1.0.0 | Table `tab:latest` |
| [`2_swat4j_vs_sysjava/`](2_swat4j_vs_sysjava/README.md) | SysJava vs SWAT4J on 10 JDK 8 images: 5 rebuilt on Debian 10 + Temurin 8 (Storm 2.4.0, Solr 8.7.0, Elasticsearch 7.5.2, Groovy 4.0.0, Jetty 9.4.51) and 5 official JDK 8 images (ZooKeeper 3.4.14, Tomcat 7.0, Cassandra 3.0.29, OrientDB 3.2.19, JRuby 9.4.2.0), plus the SWAT4J allowlists | Table `tab:results` |
| [`3_sysjava_vs_confine/`](3_sysjava_vs_confine/README.md) | SysJava vs Confine (to be added) | Table `tab:confine` |
| `Results/` | Results of the original submission, kept unchanged | submitted version |
| [`docker_images/`](docker_images/README.md) | Every image used, with its digest, image ID, OS and JDK; the Dockerfiles of the rebuilt Debian 10 + JDK 8 images and a pinned build script | |
| `echotrace/` | Tool source: the bytecode analysis (Java, Maven). Commit in `echotrace/COMMIT` | |
| `echotrace_516fb46/` | The same tool one commit earlier, before the `<clinit>` fix. Stage 4 of seven latest-version results was run with it (`pipeline_run.log`: "code at 516fb46"); `whitelist.sh` uses it for those images | |
| [`syspart/`](syspart/README.md) | Which SysPart build is used and how to build it (SysPart is a third-party tool) | |
| [`swat4j/`](swat4j/README.md) | Scripts that run the SWAT4J baseline unmodified (its allowlists are added with the results) | |
| `analysis/` | Native-declaration coverage audit (`coverage.sh`) | coverage rows of both tables |
| `tools/` | `make_tables.py` (results to table rows); `replay_syspart.py`, `whitelist_from_callgraphs.py` (used by `whitelist.sh`); `build_artifact.sh`, `docker_images.sh`, `anonymise.sh` (how this folder was assembled) | |
| `whitelist.sh` | Static reproduction of one image's allowlist from the shipped dataset and call graphs, without SysPart (level B below) | profiles in both tables |
| `setup.sh` | One-time setup for the full rerun (level C): checks tools, builds `echotrace/`, prepares `work/latest` and `work/jdk8` | |

Each result folder (`<folder>/results/<image>/` or `sysjava_results/<image>/`) has
the same layout:

```
Dynamic_Analysis/sysdig_outputs_<image>/   what the container loaded/executed (sysdig capture)
Bytecode_Analysis/outputs_<image>/         native declarations and their bindings
    native_methods.txt                     every native method declaration reached
    mapped_method_syscalls.txt             declaration -> native symbol -> library
    jvm_dynamic_mapping.txt, jni_dynamic_bindings.txt   RegisterNatives tables
    jna_hits.txt, jnr_ffi_hits.txt, ffi_hits.txt        JNA / JNR-FFI / FFM bindings
Binary_Analysis/
    syscalls_output_<image>/<lib>/         SysPart per library: callgraph.json.gz, syscalls.txt
    syscalls_output_<image>/<image>.json   THE GENERATED SECCOMP PROFILE
    syscalls_BIN_<image>/<exe>/            SysPart per executed binary
    syscalls_unanalysed_<image>/           loaded libraries without a binding (fallback)
    jna_ffi_analysis/                      SysPart from JNA/FFI entry points
Reports/                                   leftover / unanalysed-library reports
pipeline_run.log                           full log of the run
seccomp_runtime_test.log                   the container restarted under its profile (RESULT=PASS/FAIL)
named_callgraph_summary.tsv                functions / unnamed functions / syscalls per SysPart result
debug_symbols.tsv                          which ELF got debug symbols from where
detector_commit.txt                        detector commit of stage 4, when it differs from the default
jni_overload_check.tsv                     overloaded JNI methods and how each was mapped
dataset/Dataset.tar.xz.partNN              the files copied out of the container (below)
```

`callgraph.json` and `allfunctions.txt` files are gzipped (`gunzip -k`).

`dataset/` holds the files the run copied out of the container, as an xz
archive split into 45 MB parts: `Dataset/JARFILES_<image>/` (JARs),
`LIBS_<image>/` (native libraries, with the JDK's under `JDK*_LIBS/`),
`BINARIES_<image>/` (executables), `RUNTIME_<image>/` (the container's Java
runtime), and `Dataset_symbolized/LIBS_<image>/_container_deps/` (libraries
stage 6 added from the container because a copied library needs them). They are
copies of files from public Docker images. Unpack with
`cat dataset/Dataset.tar.xz.part* | xz -dc | tar -x`. The copies with restored
debug symbols are not shipped (stage 6 recreates them; `debug_symbols.tsv`
says where each came from).

## Reproducing the tables

There are three levels, from fastest to complete:

| | What it reruns | Needs | Time per image |
|---|---|---|---|
| A | table rows from the shipped results | Python | seconds |
| B | bytecode analysis and native mapping on the shipped dataset, syscalls from the shipped call graphs, seccomp profile | JDK 17+, Maven, Python, binutils, xz | 5-15 min |
| C | the whole pipeline, including the sysdig capture and SysPart | everything below, root | 2-8 h |

### A. Rebuild the tables from the shipped results (no setup; once results are added)

```bash
python3 tools/make_tables.py latest 1_latest_containers/results \
    --runtime 1_latest_containers/runc.txt --out /tmp/latest_table
python3 tools/make_tables.py jdk8 2_swat4j_vs_sysjava/sysjava_results \
    --runtime 2_swat4j_vs_sysjava/runc.txt 2_swat4j_vs_sysjava/runc_host_1.3.4_additions.txt \
    --out /tmp/jdk8_table
```

These commands print the syscall-allowlist rows (Java library, container binary,
runtime, library fallback, total) and the artefact rows (libraries, executables
and JARs observed; libraries analysed). They also check that each profile equals
the union of its parts. Once results are added, the output for the shipped
results will be in `<folder>/tables/`.

### B. Rebuild the allowlists from the shipped dataset and call graphs (no SysPart, no Docker, no root)

The files each run copied out of its container (`dataset/`) and SysPart's call
graph of every analysed library and executable (`callgraph.json.gz`, with the
syscall sites in `syscalls_with_callsites*.txt`) are shipped. `whitelist.sh`
reruns SysJava's own analysis on that dataset and parses those call graphs
instead of running SysPart:

```bash
./whitelist.sh zookeeper_3.9.5     # one image (folder name from either table)
./whitelist.sh all                 # every image with shipped results
```

For one image it:

1. unpacks the shipped dataset into `work/static/<image>/`;
2. (only if the image has no shipped dataset, or with `FROM_CONTAINER=1`) starts
   the pinned image (`docker_images/images.tsv`) instead and copies out the files
   listed in the shipped sysdig capture (`Dynamic_Analysis/`); this needs Docker;
3. runs the bytecode analysis, giving `native_methods.txt` and the JNI, JNA,
   JNR-FFI and FFM bindings. It uses the detector commit the shipped result was
   made with (`echotrace/` or `echotrace_516fb46/`, built with Maven on first use);
4. maps native methods to native symbols, giving the start functions per library;
5. follows each shipped call graph from those start functions to the reachable
   syscalls (`tools/replay_syspart.py`, the same breadth-first search as
   `scripts/getsyscalls_lowmem.py`);
6. merges them with the runtime set into the seccomp profile (`scripts/merge_all_syscalls.py`);
7. compares the profile with the shipped one.

Output: `<table folder>/whitelists_static/<image>.json`, `<image>.diff.txt`
(syscalls only in the rerun or only in the shipped profile) and
`<image>.report.tsv` (one line per call graph). A call graph covers only what is
reachable from the start functions SysPart was run with. If the bytecode
analysis finds a start function or library the shipped call graphs do not
cover, the report says so (`starts_not_in_callgraph`,
`new_library_needs_syspart`); that part needs level C.

Checked on the five finished latest-version images: all 141 call graphs give
the same syscalls as SysPart did. ZooKeeper 3.9.5 rerun from its shipped dataset
(no Docker, 6 minutes) gives the same native methods (735), all 35 call graphs
ok, and the same profile apart from `set_tid_address`, which was added to
`runc.txt` after that run. JRuby 10.1.0.0 (detector `52628c4`) gives the same
460 native methods, all 22 call graphs ok, and an identical profile (173 syscalls).

### C. Rerun everything

Requirements:

* Linux x86-64 host, root access via sudo (sysdig and the seccomp runtime check)
* Docker 24+ and sysdig 0.38+ with the modern eBPF probe (`sysdig --modern-bpf`)
* JDK 17+, Maven 3.8+, Python 3.10+, binutils, elfutils (`eu-unstrip`, `debuginfod-find`), `dpkg-deb`, curl, git
* SysPart built as described in [`syspart/README.md`](syspart/README.md)
* At least 8 cores, 64 GB RAM plus swap, and 100 GB of free disk. One SysPart run
  on a full `libjvm.so` needs 20-35 GB of memory. A whole image takes 2-8 hours.
* Network access: Docker Hub images, Debian/Ubuntu debug-symbol archives, debuginfod

Steps:

```bash
SYSPART_ROOT=/path/to/SysPartCode ./setup.sh   # once
1_latest_containers/reproduce.sh               # Table tab:latest:  SysJava on 10 images, prints the table
2_swat4j_vs_sysjava/reproduce.sh               # Table tab:results: SysJava and SWAT4J on 10 JDK 8 images, prints the table
analysis/coverage.sh latest                    # native-declaration coverage rows
analysis/coverage.sh jdk8
AUDIT=analysis/coverage_latest/per_app_summary.csv TABLE_ONLY=1 1_latest_containers/reproduce.sh
AUDIT=analysis/coverage_jdk8/per_app_summary.csv   TABLE_ONLY=1 2_swat4j_vs_sysjava/reproduce.sh
```

One script per table: it runs every tool the table compares and writes the
finished table to `<folder>/tables_rerun/`. Table `tab:confine` will get its own
script in `3_sysjava_vs_confine/` with the Confine comparison.
Each `reproduce.sh` takes image names to run a subset. `STAGE=<n>` resumes an
image from pipeline stage *n*. A failed stage does not stop the other images.

Pipeline stages, the same for every image (`1_latest_containers/scripts/run_latest_target.sh`, `2_swat4j_vs_sysjava/scripts/run_jdk8_target.sh`):

| Stage | What runs | Main script |
|---|---|---|
| 1 | start the container | driver |
| 2 | sysdig capture of a clean start (120 s) | `sysdig_unified.sh` |
| 3 | copy the JDK, the JARs, and the loaded libraries and executables out of the container | `extract_runtime_and_jar_libs.sh` |
| 4 | bytecode analysis: native declarations, JNI/JNA/JNR-FFI/FFM bindings | `JNADetector` (echotrace/) |
| 5 | map declarations to native symbols, write SysPart start functions | `prepare_native_mapping.sh`, `check_jni_overloads.py` |
| 6 | restore debug symbols for stripped ELFs (Build ID, debuginfod, distribution `-dbgsym`/`-dbg` packages) | `symbolize_dataset.py` |
| 7 | SysPart on each mapped library and each executed binary | `automate_syscall_analysis.sh` |
| 8 | SysPart on loaded libraries with no binding (fallback) and on JNA/FFI entry points | `analyze_unanalysed_loaded_libs.py`, `analyse_jna_ffi.py` |
| 9 | count unnamed functions per call graph | driver |
| 10 | merge everything with the runtime set into the seccomp profile | `merge_all_syscalls.py`, `organize_results.sh` |
| 11 | restart the container under the profile and check that it becomes ready | `verify_seccomp_profile.sh` |

### Expected differences on a rerun

* **Dynamic capture.** sysdig records what the container loads in 120 s. On a
  heavily loaded host it can drop the JVM startup burst. The driver retries when
  no JARs, no libraries or no `libjvm.so` were captured. Paths under `/tmp` get
  random names.
* **Image drift.** Tags like `tomcat:11.0`, `orientdb:latest` and `storm:latest`
  move. `docker_images/IMAGES.md` records the digest of every image used, and
  both `reproduce.sh` scripts pull by digest. The five rebuilt JDK 8 images are
  built by `docker_images/build_jdk8_images.sh`, which pins the base image digest
  and the Temurin release (8u504-b01).
* **Debug symbols.** Their availability depends on the distribution archives at
  the time of the rerun. `debug_symbols.tsv` lists what was found and from where.
  A library without symbols still gets analysed, but its call graph has unnamed
  functions.
