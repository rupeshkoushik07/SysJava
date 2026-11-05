# 1. Latest containers (Table `tab:latest`)

These are the SysJava results for the newer releases of the studied applications,
covering JDK 8 to 25. One folder per image is in `results/`.

| Image (folder) | Docker tag | JDK | Base OS |
|---|---|---|---|
| `cassandra_5.0.8` | `cassandra:5.0.8` | 17 | Debian 12 |
| `zookeeper_3.9.5` | `zookeeper:3.9.5` | 17 | Ubuntu 22.04 |
| `tomcat_11.0.22` | `tomcat:11.0` (retagged `tomcat:11.0.22`) | 25 | Ubuntu 24.04 |
| `solr_10.0.0` | `solr:10.0.0` | 25 | Ubuntu 24.04 |
| `groovy_5.0.6` | `groovy:5.0.6` | 21 | Ubuntu 24.04 |
| `orientdb_3.2.53` | `orientdb:latest` (retagged `orientdb:3.2.53`) | 8 | Ubuntu 26.04 |
| `jetty_12.1.10` | `jetty:12.1.10` | 25 | Ubuntu 26.04 |
| `elasticsearch_7.1.0` | `docker.elastic.co/elasticsearch/elasticsearch:7.1.0` | 12 (bundled) | CentOS 7 |
| `storm_2.8.8` | `storm:latest` (retagged `storm:2.8.8`), with `zookeeper:3.9.5` | 17 | Ubuntu 26.04 |
| `jruby_10.1.0.0` | `jruby:10.1.0.0` | 21 | Ubuntu 24.04 |

`../docker_images/IMAGES.md` lists the exact digest of each image.

## Files

> The result folders are placeholders (`PENDING.md`) until the final runs are
> done; `tables/` and `STATUS.md` are added with the results.

* `scripts/`: the exact pipeline scripts used for this table (driver: `scripts/run_latest_target.sh`).
* `runc.txt`: the runtime syscall set merged into every profile.
* `results/<image>/`: one pipeline result. The layout is described in the top-level README.
  * The seccomp profile is `Binary_Analysis/syscalls_output_<image>/<image>.json`.
  * Whether the container still starts under that profile is in `seccomp_runtime_test.log`.
  * `detector_commit.txt` names the detector build used for stage 4 (see below).
* `tables/`: table rows computed from `results/` by `tools/make_tables.py`
  (`table.md`, `table.csv`, `table_rows.tex`).
* `STATUS.md`: which images are complete in this version of the artifact.
* `reproduce.sh`: reruns the pipeline and rebuilds the table.

## Reproduce

Static (no SysPart, sysdig or root; minutes per image): rebuild an image's
allowlist from the shipped call graphs, see the top-level README, level B.

```bash
../whitelist.sh zookeeper_3.9.5          # -> whitelists_static/zookeeper_3.9.5.json + .diff.txt
```

Full pipeline:

```bash
SYSPART_ROOT=/path/to/SysPartCode ../setup.sh   # once
./reproduce.sh                                  # all 10 images (2-8 h each)
./reproduce.sh tomcat_11.0.22                   # one image
STAGE=8 ./reproduce.sh solr_10.0.0              # resume an image from stage 8
TABLE_ONLY=1 ./reproduce.sh                     # only rebuild tables_rerun/ from existing results
```

The pipeline driver is `scripts/run_latest_target.sh` (in the
working copy `work/latest/`). For each image it writes
`work/latest/Final_results_latest_versions/<image>/`, in the same layout as
`results/`. To compare a rerun with the shipped table:

```bash
diff tables/table.md tables_rerun/table.md
```

Native-declaration coverage rows (declarations, accounted for, JNI static,
partial, RegisterNatives, not found, SWAT4J resolved) come from the mapping
audit. It needs the full results with `Dataset/`, so it runs after a rerun:

```bash
../analysis/coverage.sh latest
AUDIT=../analysis/coverage_latest/per_app_summary.csv TABLE_ONLY=1 ./reproduce.sh
```

## Table rows and their source files

| Row | Computed from (in `results/<image>/`) |
|---|---|
| Java Lib Syscalls | `Binary_Analysis/syscalls_output_<image>/library_syscalls.txt` ∪ `Binary_Analysis/jna_ffi_analysis/union_syscalls.txt` |
| Container Binary Syscalls | `Binary_Analysis/syscalls_BIN_<image>/binary_syscalls.txt` |
| Runtime Set, Additional | `runc.txt` (in this folder) minus the two rows above |
| Library Fallback (Δ) | `Binary_Analysis/syscalls_unanalysed_<image>/unanalysed_syscalls.txt` minus all of the above |
| Total Syscalls | syscall names in the profile `<image>.json` (checked to equal the union of the four sets) |
| Libraries / Executables / JARs Observed | `Dynamic_Analysis/sysdig_outputs_<image>/libs_loaded_raw.txt`, `binaries_unique_<image>.txt`, `jars_unique_<image>.txt` |
| Libraries Analysed | number of SysPart result folders in `syscalls_output_<image>/` |
| JNA / FFI / JNR-FFI hits | `Bytecode_Analysis/outputs_<image>/jna_hits.txt`, `ffi_hits.txt`, `jnr_ffi_hits.txt` |
| Native declarations, coverage | `analysis/coverage.sh` → `per_app_summary.csv` |

## Notes

* **Detector build.** `echotrace/` (commit in `echotrace/COMMIT`) follows class
  initialisers (`<clinit>`) and resolves inherited methods. Each image's
  `detector_commit.txt` records the detector commit it was analysed with.
* **glibc ≥ 2.41.** Cancellable syscall wrappers there pass the syscall number
  through `__syscall_cancel`. `scripts/cancel_syscall_sites.py`
  recovers these call sites (OrientDB, Jetty and Storm run on glibc 2.43).
* **Runtime set.** `runc.txt` holds the syscalls the container runtime issues
  before the application starts.
