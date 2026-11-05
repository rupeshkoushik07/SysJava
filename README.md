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

> **Status:** the result folders are placeholders (`PENDING.md`) while the final
> runs finish. They will be filled with the layout described below.

## Layout

| Folder | What it holds | Paper |
|---|---|---|
| [`1_latest_containers/`](1_latest_containers/README.md) | Results for the 10 newer-version images (JDK 8-25): Cassandra 5.0.8, ZooKeeper 3.9.5, Tomcat 11.0.22, Solr 10.0.0, Groovy 5.0.6, OrientDB 3.2.53, Jetty 12.1.10, Elasticsearch 7.1.0, Storm 2.8.8, JRuby 10.1.0.0 | Table `tab:latest` |
| [`2_swat4j_vs_sysjava/`](2_swat4j_vs_sysjava/README.md) | SysJava vs SWAT4J on 10 JDK 8 images: 5 rebuilt on Debian 10 + Temurin 8 (Storm 2.4.0, Solr 8.7.0, Elasticsearch 7.5.2, Groovy 4.0.0, Jetty 9.4.51) and 5 official JDK 8 images (ZooKeeper 3.4.14, Tomcat 7.0, Cassandra 3.0.29, OrientDB 3.2.19, JRuby 9.4.2.0), plus the SWAT4J allowlists | Table `tab:results` |
| [`3_sysjava_vs_confine/`](3_sysjava_vs_confine/README.md) | SysJava vs Confine (to be added) | Table `tab:confine` |
| `Results/` | Results of the original submission, kept unchanged | submitted version |
| [`docker_images/`](docker_images/README.md) | Every image used, with its digest, image ID, OS and JDK; the Dockerfiles of the rebuilt Debian 10 + JDK 8 images and a pinned build script | |
| `echotrace/` | Tool source: the bytecode analysis (Java, Maven). Commit in `echotrace/COMMIT` | |
| `echotrace_patches/` | The detector fix (`<clinit>` and inherited methods) as a patch, to rebuild the earlier detector | |
| `pipelines/latest/`, `pipelines/jdk8/` | The exact driver and pipeline scripts used for folders 1 and 2 | |
| [`syspart/`](syspart/README.md) | Which SysPart build is used and how to build it (SysPart is a third-party tool) | |
| [`swat4j/`](swat4j/README.md) | Scripts that run the SWAT4J baseline unmodified (its allowlists are added with the results) | |
| `analysis/` | Native-declaration coverage audit (`coverage.sh`) | coverage rows of both tables |
| `tools/` | `make_tables.py` (results to table rows); `build_artifact.sh`, `docker_images.sh`, `anonymise.sh` (how this folder was assembled) | |
| `setup.sh` | One-time setup: checks tools, builds `echotrace/`, prepares `work/latest` and `work/jdk8` | |

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
```

`callgraph.json` files are gzipped (`gunzip -k`). The container file copies
(`Dataset/`: JARs, `.so` files, executables, with and without debug symbols) are
not shipped. They are copies of files from public Docker images and the pipeline
recreates them on a rerun.

## Reproducing the tables

There are two levels. Rebuilding a table from the shipped results takes seconds.
Rerunning the pipeline takes hours per image.

### A. Rebuild the tables from the shipped results (no setup; once results are added)

```bash
python3 tools/make_tables.py latest 1_latest_containers/results \
    --runtime pipelines/latest/runc.txt --out /tmp/latest_table
python3 tools/make_tables.py jdk8 2_swat4j_vs_sysjava/sysjava_results \
    --runtime pipelines/jdk8/runc.txt pipelines/jdk8/runc_host_1.3.4_additions.txt \
    --out /tmp/jdk8_table
```

These commands print the syscall-allowlist rows (Java library, container binary,
runtime, library fallback, total) and the artefact rows (libraries, executables
and JARs observed; libraries analysed). They also check that each profile equals
the union of its parts. Once results are added, the output for the shipped
results will be in `<folder>/tables/`.

### B. Rerun everything

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
1_latest_containers/reproduce.sh               # Table tab:latest   (10 images)
2_swat4j_vs_sysjava/reproduce.sh               # Table tab:results  (10 JDK 8 images)
analysis/coverage.sh latest                    # native-declaration coverage rows
analysis/coverage.sh jdk8
AUDIT=analysis/coverage_latest/per_app_summary.csv TABLE_ONLY=1 1_latest_containers/reproduce.sh
AUDIT=analysis/coverage_jdk8/per_app_summary.csv   TABLE_ONLY=1 2_swat4j_vs_sysjava/reproduce.sh
```

Each `reproduce.sh` takes image names to run a subset. `STAGE=<n>` resumes an
image from pipeline stage *n*. A failed stage does not stop the other images.

Pipeline stages, the same for every image (`pipelines/*/scripts/run_*_target.sh`):

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
