# Workload validation of the JDK 8 profiles

Does each application still work under the seccomp profile SysJava generated for it, and does it make
any syscall the profile does not allow? Each of the ten JDK 8 images (Debian 10, Temurin 8u504, the
images of `2_swat4j_vs_sysjava/`) runs a real workload in three modes, three times each (90 runs per
profile set):

| Mode | Seccomp profile | What it shows |
|---|---|---|
| `base` | Docker's default profile | the workload itself works (reference operation count) |
| `log` | the generated profile with `defaultAction` set to `SCMP_ACT_LOG` | nothing is blocked; every syscall outside the profile is written to the kernel audit log |
| `enforce` | the generated profile as published (`defaultAction` `SCMP_ACT_ERRNO`) | the application works when everything else is denied |

**PASS** for an application means, in every repetition:
1. `enforce` completes the same number of operations as `base`;
2. no operation fails in any mode;
3. the `log` run records no syscall outside the profile.

Rule 3 is strict: under `enforce` such a syscall gets `EPERM`, and an application that ignores the error
still passes rules 1 and 2. Log mode is the only way to see it.

Two profile sets were tested:

| Set | Folder | Profiles |
|---|---|---|
| `paper` | `profiles/paper/` | the profiles of tab:results (Storm: 172, without the false-FFM `sync`) |
| `fixed` | `profiles/fixed/` | the same after three analysis fixes for the syscalls the `paper` log runs found (see "Findings") |

## How a run works (`run_validation.py`, function `one_run`)

1. Start the container: `docker run -d --name wlv-<app>-<mode>-<rep> [--security-opt seccomp=<profile>] <args> <image>`.
   Tomcat and Jetty get a fresh host directory mounted as `webapps/` (for hot deployment); Groovy and
   JRuby get `scripts/` mounted read-only at `/wl`.
2. A thread records the host PID of every process in the container (`docker top`, every second).
3. Wait until the application is ready (check per application below; at most 6 minutes).
4. Run the workload from the host, or from a separate unconfined client container, so no tool runs
   inside the confined container. Every request is counted `ok` or `failed` (expected HTTP status,
   exit code, or output). Groovy and JRuby are batch programs: the workload script is the program, and
   it prints `OPS ok=<n> fail=<n>`.
5. Save `docker logs` (`<mode>_<rep>.container.log`).
6. Log mode: read the `SCMP_ACT_LOG` records (`type=SECCOMP`, `code=0x7ffc0000`) written since the
   container started and split them by PID: this container's (`would_be_denied`) and other processes'
   (`unattributed_log_records`, e.g. another app in log mode at the same time). The raw records go to
   `<mode>_<rep>.audit.log`.
7. Write `<mode>_<rep>.json` and remove the container.

**Where the log records are.** When auditd runs, it takes the seccomp records: they are in
`/var/log/audit/audit.log`, not in the kernel log (`journalctl -k`, `dmesg`). Without auditd they go to
the kernel log as `type=1326`; `denials()` reads the audit log, so adapt it on such a host. Always run
the positive control first.

**Positive control** (`control/positive_control.py`): JRuby's log profile with `mkdir` and `rename`
removed; a JRuby one-liner makes a directory, writes a file and renames it. The harness must report
exactly `mkdir` and `rename` (`control/result*.json`, with their raw records in `*.audit.log`). It did,
both before the `paper` runs and between the `fixed` runs.

## The workloads

| App | Image, run arguments | Ready when | Workload (operations per run) |
|---|---|---|---|
| Tomcat 7 | `tomcat:7.0-jdk8-buster`; `webapps/` = the image's `webapps.dist` without manager apps | `GET /examples/` = 200 | 3,000 GETs on 12 servlet, JSP and doc pages, 16 in parallel; 50 form POSTs; hot deploy of a war (copied into `webapps/`, `GET /wl/` = 200) and undeploy (removed, 404). **3,052** |
| Jetty 9.4 | `jetty:9.4.51-jdk8-buster`; `webapps/` holds `wl.war` (Tomcat's ROOT app: static files) | `GET /wl/tomcat.css` = 200 | 3,000 GETs on 6 static files of the deployed war, 16 in parallel; 50 POSTs; hot deploy of a second war and undeploy. The image has no JSP support, so only static files are used. **3,052** |
| Elasticsearch 7.5 | `elasticsearch:7.5.2-jdk8-buster`; `ES_JAVA_OPTS=-Xms1g -Xmx1g` | `GET /_cluster/health` = 200 | per index (2): create (2 shards), 20 bulk requests of 1,000 documents, 100 searches (match, range, terms aggregation, sorted term query), forcemerge, update_by_query; then reindex into a third index and delete all three. **250** |
| Solr 8.7 | `solr:8.7.0-jdk8-buster` | `GET /solr/admin/info/system` = 200 | create core `wl`; 5 rounds of posting the image's 14 example XML documents and a 2,000-document JSON bulk; 120 queries (all, term, facet, range+sort, 500 rows, wildcard); optimize; backup; unload with index, data and instance directory deleted. **199** |
| Cassandra 3.0 | `cassandra:3.0.29-jdk8-buster`; `MAX_HEAP_SIZE=1G`, `HEAP_NEWSIZE=256M` | log line `Starting listening for CQL clients` (+10 s) | from a client container of the same image: 8 `cqlsh` statements (keyspace, table, secondary index, 200-row batch, count, indexed select, TRUNCATE, DROP KEYSPACE); `cassandra-stress` write, read and mixed (1 write : 3 reads), n=60,000 each, 16 threads. Counted per statement or stress phase. **11** |
| ZooKeeper 3.4 | `zookeeper:3.4.14-jdk8-buster` | log line `binding to port` (+3 s) | 27 four-letter-word commands (ruok, stat, srvr, conf, cons, envi, mntr, wchs, dump; 3 times); 3 `zkCli.sh` sessions from a client container, each about 1,300 commands (create 400 znodes, set, get, ls, stat, sync, sequential and ephemeral nodes, delete, rmr). **3,951** |
| OrientDB 3.2 | `orientdb:3.2.19-jdk8-buster`; `ORIENTDB_ROOT_PASSWORD=root` | `GET /listDatabases` = 200 | REST API: create database; 5 schema commands (vertex and edge classes, properties, index); 1,500 inserts; 200 edges; 100 queries (count, filter, index lookup, graph traversal); update; drop database. **1,808** |
| Storm 2.4 | `storm:2.4.0-jdk8-buster nimbus`, on network `et-jdk8-net` with a `zookeeper:3.7` container (started by the script) | Thrift port 6627 accepts connections (+10 s) | from a client container of the same image: `storm list` ×10; 5 × blobstore create, list, cat, update, delete (these reach RocksDB in nimbus). **35** |
| Groovy 4 | `groovy:4.0.0-jdk8-buster groovy /wl/workload.groovy` | (batch) | `scripts/workload.groovy`, 5 rounds of: write 200 files, read them with a regex, rename, JSON, XML, zip, a thread pool, a local HTTP server and client, delete the tree; then cleanup. **46** |
| JRuby 9.4 | `jruby:9.4.2.0-jdk8-buster jruby /wl/workload.rb` | (batch) | `scripts/workload.rb`, 5 rounds of: write 200 files, read them with a regex, rename and chmod, JSON, zlib, threads, a local TCP server and client, Java interop, delete the tree; then cleanup. **46** |

The exact requests are in `run_validation.py` (functions `wl_<app>`) and `scripts/`.

## Reproduce

Needs Docker, Python 3, sudo (to read `/var/log/audit/audit.log` and remove root-owned files that
Tomcat and Jetty leave in the mounted `webapps/`), and `ausyscall` (package `auditd`). The images are
listed, pinned by digest, in `docker_images/` (the JDK 8 images are rebuilt with
`docker_images/build_jdk8_images.sh`).

```bash
cd analysis/workload_validation
python3 control/positive_control.py control/result_check.json        # must print "passed": true
export WLV_PROFILE_DIR=$PWD/profiles/fixed WLV_RESULTS=results_rerun  # or profiles/paper
python3 run_validation.py tomcat jetty storm --reps 3 &              # apps can run in parallel,
python3 run_validation.py elasticsearch solr cassandra --reps 3 &    # one process per group
python3 run_validation.py zookeeper orientdb groovy jruby --reps 3 &
wait
python3 make_table.py                                                # -> $WLV_RESULTS/table.md
```
One run takes 1-15 minutes (Cassandra's stress phases are the longest); the 90 runs take about
2 hours in three parallel groups.

Outputs, per application and run: `<mode>_<rep>.json` (ready time, workload time, ok/failed counts and
the first error per operation, PIDs seen, would-be-denied syscalls), `<mode>_<rep>.container.log`, and
for log mode `<mode>_<rep>.audit.log`. `summary.tsv` and `table.md` summarise all runs.

## Results

| Folder | Profiles | Runs |
|---|---|---|
| `results/paper_profiles/` | `profiles/paper/` | 90, 2026-11-11 morning |
| `results/fixed_profiles/` | `profiles/fixed/` | 90, 2026-11-11 afternoon |
| `results/trace/` | `profiles/fixed/` (for "missing") | 10 traced runs under Docker's default profile, 2026-11-12 (see "Traced pass") |

`logs/` has the console output of every run. The `paper` runs' `.audit.log` files were extracted
afterwards from the host's audit log by time window (`extract_audit_records.py`), because the harness
did not save them then; records of other apps that ran at the same time are marked `# other app`.

**`paper` profiles** (`results/paper_profiles/table.md`):

| Application | Workload ops per run | Base: ok / failed | Log: ok / failed | Enforce: ok / failed | Would be blocked (log mode) | Runs | Result |
|---|---:|---|---|---|---|---:|---|
| cassandra | 11 | 33 / 0 | 33 / 0 | 33 / 0 | none | 9 | PASS |
| elasticsearch | 250 | 750 / 0 | 750 / 0 | 750 / 0 | fchown | 9 | FAIL |
| groovy | 46 | 138 / 0 | 138 / 0 | 138 / 0 | none | 9 | PASS |
| jetty | 3,052 | 9,156 / 0 | 9,156 / 0 | 9,156 / 0 | fchdir, fchown | 9 | FAIL |
| jruby | 46 | 138 / 0 | 138 / 0 | 138 / 0 | none | 9 | PASS |
| orientdb | 1,808 | 5,424 / 0 | 5,424 / 0 | 5,424 / 0 | none | 9 | PASS |
| solr | 199 | 597 / 0 | 597 / 0 | 597 / 0 | times | 9 | FAIL |
| storm | 35 | 105 / 0 | 105 / 0 | 105 / 0 | fallocate, fchdir | 9 | FAIL |
| tomcat | 3,052 | 9,156 / 0 | 9,156 / 0 | 9,156 / 0 | fchdir | 9 | FAIL |
| zookeeper | 3,951 | 11,853 / 0 | 11,853 / 0 | 11,853 / 0 | none | 9 | PASS |

**`fixed` profiles** (`results/fixed_profiles/table.md`):

| Application | Workload ops per run | Base: ok / failed | Log: ok / failed | Enforce: ok / failed | Would be blocked (log mode) | Runs | Result |
|---|---:|---|---|---|---|---:|---|
| cassandra | 11 | 33 / 0 | 33 / 0 | 33 / 0 | none | 9 | PASS |
| elasticsearch | 250 | 750 / 0 | 750 / 0 | 750 / 0 | none | 9 | PASS |
| groovy | 46 | 138 / 0 | 138 / 0 | 138 / 0 | none | 9 | PASS |
| jetty | 3,052 | 9,156 / 0 | 9,156 / 0 | 9,156 / 0 | none | 9 | PASS |
| jruby | 46 | 138 / 0 | 138 / 0 | 138 / 0 | none | 9 | PASS |
| orientdb | 1,808 | 5,424 / 0 | 5,424 / 0 | 5,424 / 0 | none | 9 | PASS |
| solr | 199 | 597 / 0 | 597 / 0 | 597 / 0 | none | 9 | PASS |
| storm | 35 | 105 / 0 | 105 / 0 | 105 / 0 | none | 9 | PASS |
| tomcat | 3,052 | 9,156 / 0 | 9,156 / 0 | 9,156 / 0 | none | 9 | PASS |
| zookeeper | 3,951 | 11,853 / 0 | 11,853 / 0 | 11,853 / 0 | none | 9 | PASS |

## Traced pass: the policy-validation table (`results/trace/`)

The columns of the paper's policy-validation table: syscalls missing / performed / permitted, and new
binaries / libraries. `trace_validation.py` runs each workload once more under Docker's default seccomp
profile while sysdig (0.41.4, `--modern-bpf`) records every syscall of the container, from start-up to
the end of the workload (2026-11-12, `fixed` profiles):

- **performed**: the distinct syscalls of the container's processes. sysdig's names are mapped to
  libseccomp's (`pread` -> `pread64`, `pwrite` -> `pwrite64`, `prlimit` -> `prlimit64`). runc's setup
  stages `runc:[0:PARENT]` and `runc:[1:CHILD]` are left out because they run before the filter is
  installed (listed in `runc_setup_syscalls`).
- **missing**: performed syscalls that the published profile does not allow (Storm: the 179 profile).
- **permitted**: the size of the profile.
- **new**: programs executed and `.so` files opened whose name is not in the image's dataset
  (`Dataset/LIBS_<t>`, `Dataset/BINARIES_<t>`). Three loads use another name of an analysed library and
  are listed in `loaded_under_other_name`:
  - Cassandra's `/tmp/libnetty-transport-native-epoll<n>.so`;
  - Cassandra's `/usr/local/lib/libjemalloc.so` (`libjemalloc.so.2`);
  - OrientDB's `/tmp/jffi<n>.so` (`libjffi-1.2.so`).

| Container | Workload (ops) | Missing / performed / permitted | New binaries / libraries |
|---|---|---|---|
| Zookeeper 3.4.14 | zkCli + four-letter cmds (3,951) | 0 / 85 / 192 | 0 / 0 |
| Tomcat 7.0 | servlet/JSP GETs, POSTs, war deploy (3,052) | 0 / 82 / 173 | 0 / 0 |
| Cassandra 3.0.29 | cqlsh + cassandra-stress (11) | 0 / 104 / 230 | 0 / 0 |
| Jetty 9.4.51 | static GETs, POSTs, war deploy (3,052) | 0 / 67 / 161 | 0 / 0 |
| Storm 2.4.0 | storm list + blobstore (35) | 0 / 93 / 179 | 0 / 0 |
| OrientDB 3.2.19 | REST CRUD, index, edges (1,808) | 0 / 79 / 174 | 0 / 0 |
| Elasticsearch 7.5.2 | bulk index, search, reindex (250) | 0 / 88 / 185 | 0 / 0 |
| Solr 8.7.0 | index, query, backup, unload (199) | 0 / 86 / 201 | 0 / 0 |
| Groovy 4.0.0 | script: files, XML, zip, HTTP (46) | 0 / 79 / 189 | 0 / 0 |
| JRuby 9.4.2.0 | script: files, JSON, zlib, TCP (46) | 0 / 78 / 168 | 0 / 0 |

Every workload completed with the same operation count as the validation runs. Per application,
`results/trace/<app>/` holds the trace (`trace_1.sysdig.txt`, one line per distinct syscall and process,
plus every open and execve), the run (`trace_1.json`, `trace_1.container.log`) and the row
(`table_row.json`).

```bash
cd analysis/workload_validation
python3 trace_validation.py zookeeper tomcat cassandra jetty storm orientdb elasticsearch solr groovy jruby
python3 results/trace/make_table.py          # -> results/trace/table.md, policy_validation_rows.tex
```
Needs sysdig with `--modern-bpf` and passwordless sudo for it. For the "new" column, set `WLV_DATASETS` to
a folder holding `<t>/Dataset/`. Unpack each image's dataset from
`2_swat4j_vs_sysjava/sysjava_results/<t>/dataset/` (`cat Dataset.tar.xz.part* | tar -xJ`).
`python3 trace_validation.py --analyse <apps>` recomputes the rows from the saved traces without
running anything.

## Findings (`paper` profiles) and the fixes (`fixed` profiles)

All applications completed every operation under `enforce` in all runs. Log mode showed that five
applications make syscalls their `paper` profile does not allow. Under `enforce` these get `EPERM`,
and the application (or runc) carries on:

| Syscall | Apps | Made by (evidence) | Why the analysis missed it | Fix |
|---|---|---|---|---|
| `fchdir` | Tomcat, Jetty, Storm | libjvm, `PerfMemory::create_memory_region` at JVM start-up (hsperfdata directory) | The java launcher binds libjvm through `dlsym`, so the JVM's start-up code and internal threads are not reachable from libjvm's JNI start functions | libjvm makes every syscall through functions it imports. SysPart runs on each library libjvm imports from (libc, libpthread, libdl, libm, ld-linux), from only those functions (`analyse_jvm_imports.sh`, stage 8) |
| `times` | Solr | libjvm, G1's GC-pause timing (`TraceCPUTime`); Solr runs with GC logging (`control/strace_solr.txt`, `strace -k`) | as above | as above |
| `fallocate` | Storm | RocksDB, `PosixWritableFile::Allocate` | reached only by a virtual call; RocksDB's `PosixEnv` vtable is loaded through the GOT, so SysPart does not treat its functions as address-taken | the functions a C++ library's vtables point to become start functions of that library (`add_vtable_starts.py`, stage 7; not libjvm) |
| `fchown` | Elasticsearch, Jetty | runc's init (`exe=/runc`), before the application starts | runc changes the owner of the container's stdio when the image runs as a non-root user without a terminal, and ignores the error; runc is covered by a whitelist, which lacked it | `fchown` added to `runc.txt` |

The fixes add 0 to 7 syscalls per profile (mean 183.0 -> 185.2):

| | ZooKeeper | Tomcat | Cassandra | Jetty | Storm | OrientDB | Elasticsearch | Solr | Groovy | JRuby |
|---|---|---|---|---|---|---|---|---|---|---|
| `paper` | 190 | 170 | 230 | 157 | 172 | 173 | 183 | 199 | 189 | 167 |
| `fixed` | 192 | 173 | 230 | 161 | 179 | 174 | 185 | 201 | 189 | 168 |

Added: `rt_sigsuspend` and `times` (libjvm imports) where no other part of the profile had them;
`fchdir` (Tomcat, Jetty, Storm); `fchown` (Jetty, Storm, OrientDB, Elasticsearch, JRuby); for Storm also
`fallocate`, `readahead` and `sync_file_range` (RocksDB, which goes from 59 to 70 syscalls).

## Harness problems found and fixed during the `paper` runs

None was a profile problem; each also failed under `base`:
- Log mode first read the kernel log (`journalctl -k`), where this host's auditd leaves nothing; every
  log run reported nothing. The positive control exposed it; all log runs were redone.
- Jetty: the readiness check requested a JSP, which this image cannot serve (HTTP 500 in every mode).
- Storm: nimbus logs to a file, so the log-based readiness check never fired; it now waits for port 6627.
- Smaller workload fixes: Solr query encoding and backup location, a Groovy GString, a JRuby
  `Range#sum` bug in threads, root-owned Tomcat and Jetty work directories.

## Files

| File | Purpose |
|---|---|
| `run_validation.py` | the harness: containers, readiness, workloads, log-record attribution |
| `make_table.py` | `table.md` from the run JSONs |
| `scripts/workload.groovy`, `scripts/workload.rb` | the batch workloads |
| `control/positive_control.py` | the log-mode positive control |
| `control/strace_*.txt`, `trace_callers.py` | `strace -f -k` stack traces of the missed syscalls (how `times` and `fchdir` were attributed to libjvm) |
| `extract_audit_records.py` | raw audit records for runs made before the harness saved them |
| `profiles/paper/`, `profiles/fixed/` | the profiles tested |
| `results/`, `logs/` | every run |
| `trace_validation.py`, `results/trace/` | the traced pass (policy-validation table) |
| `Workload_validation_and_binding_JDK8.pdf` | the same validation (`paper` profiles) and the binding ablation, as a report |
| `Workload_validation_all20.pdf` | the validation of all 20 profiles (this folder and `../workload_validation_latest/`), before and after the fixes |
| `Benchmarks_and_reproduction.pdf` | what each workload does, how a run works, the results with the published profiles (all 20 containers, and the traced table) and how to reproduce every step |
