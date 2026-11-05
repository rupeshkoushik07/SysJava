# 2. SWAT4J vs SysJava on JDK 8 (Table `tab:results`)

SWAT4J only supports JDK 8, so this comparison uses ten JDK 8 images.

**Five official images that already ship JDK 8**, used unchanged:

| Image (folder) | Docker tag | OS | JDK |
|---|---|---|---|
| `zookeeper_3.4.14` | `zookeeper:3.4.14` | Debian 10 | 8u292 |
| `tomcat_7.0` | `tomcat:7.0` | Debian 10 | 8u292 |
| `cassandra_3.0.29` | `cassandra:3.0.29` | Ubuntu 22.04 | 8u402 |
| `orientdb_3.2.19` | `orientdb:3.2.19` | Ubuntu 22.04 | 8u372 |
| `jruby_9.4.2.0` | `jruby:9.4.2.0` | Ubuntu 20.04 | 8u372 |

**Five images rebuilt on Debian 10 (buster) with Eclipse Temurin 8u504-b01.**
Their official images ship JDK 11-17. Each keeps the official application layout
and start command; only the OS and JDK change. The Dockerfiles and a pinned build
script are in [`../docker_images/`](../docker_images/README.md).

| Image (folder) | Local tag | Started as |
|---|---|---|
| `storm_2.4.0-jdk8-buster` | `storm:2.4.0-jdk8-buster` | `storm nimbus`, with `zookeeper:3.7` on network `et-jdk8-net` |
| `solr_8.7.0-jdk8-buster` | `solr:8.7.0-jdk8-buster` | default |
| `elasticsearch_7.5.2-jdk8-buster` | `elasticsearch:7.5.2-jdk8-buster` | `ES_JAVA_OPTS=-Xms1g -Xmx1g` |
| `groovy_4.0.0-jdk8-buster` | `groovy:4.0.0-jdk8-buster` | `groovysh` |
| `jetty_9.4.51-jdk8-buster` | `jetty:9.4.51-jdk8-buster` | default |

Digests and image IDs of all of them: `../docker_images/IMAGES.md`.

## Files

> The result folders are placeholders (`PENDING.md`) until the final runs are
> done; `tables/` and `STATUS.md` are added with the results.

* `scripts/`: the exact pipeline scripts used for this table (driver: `scripts/run_jdk8_target.sh`).
* `runc.txt` + `runc_host_1.3.4_additions.txt`: the runtime syscall set merged into every profile.
* `sysjava_results/<image>/`: SysJava pipeline result. The layout is described in
  the top-level README. The profile is
  `Binary_Analysis/syscalls_output_<image>/<image>.json`, and the runtime check is
  `Binary_Analysis/syscalls_output_<image>/seccomp_runtime_test.log`.
* `sysjava_results/_before_clinit_fix/`, `_after_clinit_fix/`: the detector's
  `native_methods.txt` before and after the `<clinit>`/inherited-method fix.
* `sysjava_results/_native_recall/`: ground truth for the detector. These are the
  native methods actually bound at run time (`java -verbose:jni`), compared with
  what the detector found.
* `../swat4j/outputs/`: SWAT4J allowlists, produced by running SWAT4J unmodified:
  * `static_host/`: SWAT4J's static analysis (JTracer and binary analyser)
  * `dynamic/`: SWAT4J's dynamic analysis (strace on containerd during startup)
  * `comparison/`: per-app shared / SysJava-only / SWAT4J-only syscalls
* `tables/`: SysJava rows computed by `tools/make_tables.py`.
* `STATUS.md`: which images are complete. Folders of images whose final run is not
  done yet contain only `PENDING.md`.

## Reproduce

Static (no SysPart, sysdig or root; minutes per image): rebuild an image's
allowlist from the shipped call graphs, see the top-level README, level B.

```bash
../whitelist.sh jetty_9.4.51-jdk8-buster          # -> whitelists_static/jetty_9.4.51-jdk8-buster.json + .diff.txt
```

Full pipeline:

One command runs SysJava (with SysPart) and SWAT4J (static and dynamic) on the
ten images and prints the finished table:

```bash
SYSPART_ROOT=/path/to/SysPartCode ../setup.sh   # once
./reproduce.sh                                  # SysJava + SWAT4J on all 10 images, then the tables
./reproduce.sh jetty_9.4.51-jdk8-buster         # one image
STAGE=7 ./reproduce.sh solr_8.7.0-jdk8-buster   # resume SysJava from stage 7
SKIP_SWAT4J=1 ./reproduce.sh                    # SysJava only
SKIP_SYSJAVA=1 ./reproduce.sh                   # SWAT4J only (needs a SysJava rerun's Dataset/)
TABLE_ONLY=1 ./reproduce.sh                     # only the tables, from existing results
```

It writes to `tables_rerun/`:

* `sysjava_vs_swat4j.md` / `.tex`: Table `tab:results`: SysJava total (A),
  SWAT4J static + dynamic (B) and its two parts, A ∩ B, A ∖ B, B ∖ A
  (`tools/swat4j_table.py`, which runs `swat4j/make_paper_table.py`);
* `table.md`, `table.csv`, `table_rows.tex`: the SysJava breakdown rows
  (`tools/make_tables.py`).

For any part that was not rerun, the tables use the shipped results
(`sysjava_results/`, `../swat4j/outputs/`), and the script prints which
folders it used. SWAT4J's one-time setup (`../swat4j/setup_swat4j.sh`) runs on
first use; its dynamic analysis traces containerd with `strace`, so it needs sudo.

The driver is `scripts/run_jdk8_target.sh`. Results go to
`work/jdk8/Final_results_JDK8/<image>/`. Its stages are numbered
1-10: there is no separate unnamed-function count, so stage 9 is the profile
merge and stage 10 the runtime check (stages 10 and 11 in the latest pipeline).

### SWAT4J side

SWAT4J (https://github.com/facumolina/SWAT4J, commit `6929d66`) is the baseline.
It is run **unmodified**: no bug fixes, and no workarounds for crashes or missing
coverage. Only its environment is provided. That means OpenJDK 8 on the host, plus
the paths it hard-codes (`/home/mrx/Desktop`, `/usr/local/apr/lib`), which are
bind-mounted in a private mount namespace per application.

```bash
../swat4j/setup_swat4j.sh          # once (reproduce.sh runs it if needed): clone + compile SWAT4J, needs openjdk-8-jdk
SKIP_SYSJAVA=1 ./reproduce.sh      # SWAT4J on all ten images, then the table
```

* Static: `swat4j/run_swat4j_host.sh <image>...` runs SWAT4J on the same JARs and
  libraries SysJava analysed. Output goes to `swat4j/rerun_host/output-syscalls/`.
* Dynamic: `swat4j/dynamic_swat4j.sh <app>...` follows the SWAT4J paper. It runs
  `strace -f -c` on containerd while the image starts and stops at the ready log
  line. Output goes to `swat4j/dynamic/`.
* Native coverage (SWAT4J Resolved / Not Found): `analysis/coverage.sh jdk8` runs
  SWAT4J's JNI mapper (`swat4j/swat4j_mapping.py`, a port of its
  `binary_analyser.py` mapping) on the same `native_methods.txt` as SysJava.

## Table rows and their source files

The syscall and artefact rows come from the same files as in
`1_latest_containers/README.md`. The runtime set here is `runc.txt` plus
`runc_host_1.3.4_additions.txt`: four syscalls issued by the init of the host's
runc 1.3.4 (`openat2`, `close_range`, `faccessat2`, `getppid`). They were measured
with the profile in log mode, and the README beside that file explains how.

## Notes

* The five official images run through the same driver
  (`scripts/run_jdk8_target.sh`). Only their image, run options
  and ready log line are added; the pipeline is the same. JRuby's `irb` prints
  no ready line, so it counts as ready once its JVM has run for 30 s.
* SysPart call graphs of stripped libraries get their function names from the
  debug symbols restored in stage 6. `debug_symbols.tsv` lists, per ELF, where its
  symbols came from or why none were found.
