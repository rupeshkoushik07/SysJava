# Workload validation of the latest-version profiles (Table III)

The same validation as [`../workload_validation/`](../workload_validation/README.md) (the JDK 8 images), on
the ten newer images of `1_latest_containers/` (JDK 8 to 25). Each image runs a real workload in three
modes, three times each (90 runs per profile set):

| Mode | Seccomp profile |
|---|---|
| `base` | Docker's default profile |
| `log` | the generated profile with `defaultAction` `SCMP_ACT_LOG`: nothing blocked, every syscall outside the profile logged by the kernel audit subsystem and attributed to the container by its PIDs |
| `enforce` | the generated profile as published |

**PASS** in every repetition: `enforce` completes the same operations as `base`, no operation fails, and
the `log` run records no syscall outside the profile. How a run works, where the log records are, and the
positive control are described in `../workload_validation/README.md`.

## The workloads

| App | Image, arguments | Ready when | Workload (operations per run) |
|---|---|---|---|
| Tomcat 11.0.22 (JDK 25) | `tomcat:11.0.22`; `webapps/` = the image's `webapps.dist` without the manager apps, and without the `RemoteCIDRValve` that Tomcat 10.1+ puts on the examples and docs apps (it allows only localhost) | `GET /examples/` = 200 | 3,000 GETs on 12 servlet, JSP and doc pages, 16 in parallel; 50 form POSTs; war hot deploy and undeploy. **3,052** |
| Jetty 12.1.10 (JDK 25) | `jetty:12.1.10` as shipped: no deploy module and no webapps, the configuration SysJava analysed | any HTTP answer | the bare server: 3,000 GETs (404), 16 in parallel; 50 POSTs with 2 KB bodies; HEAD, OPTIONS, PUT, DELETE; 20 keep-alive connections of 50 requests; a 20 KB header (431). **3,075** |
| Elasticsearch 7.1.0 (JDK 12) | `discovery.type=single-node`, 1 GB heap | `GET /_cluster/health` = 200 | 2 indices × 20 bulk requests of 1,000 documents, 100 searches each, forcemerge, update_by_query; reindex; delete. **250** |
| Solr 10.0.0 (JDK 25) | `solr:10.0.0` (SolrCloud mode with embedded ZooKeeper, Solr 10's default) | `GET /solr/admin/info/system` = 200 | Collections API: create a collection; 5 rounds of the image's 13 example XML documents and a 2,000-document JSON bulk; 120 queries; optimize; backup; delete the collection. **194** |
| Cassandra 5.0.8 (JDK 17) | 1 GB heap | log line `Startup complete` | from a client container: 8 `cqlsh` statements; `cassandra-stress` write, read and mixed, n=60,000 each. **11** |
| ZooKeeper 3.9.5 (JDK 17) | `zookeeper:3.9.5` | log line `binding to port` | 27 four-letter-word commands (only `srvr` is whitelisted by default; the others answer "not in the whitelist"); 3 `zkCli.sh` sessions of about 1,300 commands. **3,951** |
| OrientDB 3.2.53 (JDK 8) | `ORIENTDB_ROOT_PASSWORD=root` | `GET /listDatabases` = 200 | REST: database, schema, 1,500 inserts, 200 edges, 100 queries, update, drop. **1,808** |
| Storm 2.8.8 (JDK 17) | `storm nimbus` on network `et-latest-net` with a `zookeeper:3.9.5` container (started by the script) | Thrift port 6627 | `storm list` ×10; 5 × blobstore create, list, cat, update, delete. **35** |
| Groovy 5.0.6 (JDK 21) | `groovy /wl/workload.groovy` | (batch) | `scripts/workload.groovy` (as JDK 8). **46** |
| JRuby 10.1.0.0 (JDK 21) | `jruby /wl/workload.rb` | (batch) | `scripts/workload.rb` (as JDK 8). **46** |

## Reproduce

```bash
cd analysis/workload_validation_latest
python3 -c "import run_validation as r; r.prepare()"    # inputs once, before parallel runs
python3 control/positive_control.py control/result_check.json   # "passed": true
export WLV_PROFILE_DIR=$PWD/profiles/fixed WLV_RESULTS=results_rerun   # or profiles/before_fixes
python3 run_validation.py tomcat jetty storm --reps 3 &
python3 run_validation.py elasticsearch solr cassandra --reps 3 &
python3 run_validation.py zookeeper orientdb groovy jruby --reps 3 &
wait
python3 make_table.py                                   # -> $WLV_RESULTS/table.md
```
Storm's profile in `profiles/` is the Table III one: the pipeline profile, plus the supplied-library
supplements, minus the false-FFM `sync`.

## Results

| Folder | Profiles |
|---|---|
| `results/before_fixes/` | `profiles/before_fixes/`: Table III as of 2026-11-07 |
| `results/fixed/` | `profiles/fixed/`: after the fixes below |

Every run has `<mode>_<rep>.json`, `.container.log`, and for log mode `.audit.log`, the raw audit records.
`logs/` has the console output.

**Before the fixes** (`results/before_fixes/table.md`):

| Application | Workload ops per run | Base: ok / failed | Log: ok / failed | Enforce: ok / failed | Would be blocked (log mode) | Runs | Result |
|---|---:|---|---|---|---|---:|---|
| cassandra | 11 | 33 / 0 | 33 / 0 | 33 / 0 | openat2 | 9 | FAIL |
| elasticsearch | 250 | 750 / 0 | 750 / 0 | 750 / 0 | close_range, faccessat2, openat2 | 9 | FAIL |
| groovy | 46 | 138 / 0 | 138 / 0 | 138 / 0 | openat2 | 9 | FAIL |
| jetty | 3,075 | 9,225 / 0 | 9,225 / 0 | 9,225 / 0 | openat2 | 9 | FAIL |
| jruby | 46 | 138 / 0 | 138 / 0 | 138 / 0 | flock, openat2 | 9 | FAIL |
| orientdb | 1,808 | 5,424 / 0 | 5,424 / 0 | 5,424 / 0 | close_range, openat2 | 9 | FAIL |
| solr | 194 | 582 / 0 | 582 / 0 | 582 / 0 | openat2 | 9 | FAIL |
| storm | 35 | 105 / 0 | 105 / 0 | 105 / 0 | openat2, sync_file_range | 9 | FAIL |
| tomcat | 3,052 | 9,156 / 0 | 9,156 / 0 | 8,406 / 750 | copy_file_range, flock, openat2 | 9 | FAIL |
| zookeeper | 3,951 | 11,853 / 0 | 11,853 / 0 | 11,853 / 0 | openat2 | 9 | FAIL |

**Fixed profiles** (`results/fixed/table.md`):

| Application | Workload ops per run | Base: ok / failed | Log: ok / failed | Enforce: ok / failed | Would be blocked (log mode) | Runs | Result |
|---|---:|---|---|---|---|---:|---|
| cassandra | 11 | 33 / 0 | 33 / 0 | 33 / 0 | none | 9 | PASS |
| elasticsearch | 250 | 750 / 0 | 750 / 0 | 750 / 0 | none | 9 | PASS |
| groovy | 46 | 138 / 0 | 138 / 0 | 138 / 0 | none | 9 | PASS |
| jetty | 3,075 | 9,225 / 0 | 9,225 / 0 | 9,225 / 0 | none | 9 | PASS |
| jruby | 46 | 138 / 0 | 138 / 0 | 138 / 0 | none | 9 | PASS |
| orientdb | 1,808 | 5,424 / 0 | 5,424 / 0 | 5,424 / 0 | none | 9 | PASS |
| solr | 194 | 582 / 0 | 582 / 0 | 582 / 0 | none | 9 | PASS |
| storm | 35 | 105 / 0 | 105 / 0 | 105 / 0 | none | 9 | PASS |
| tomcat | 3,052 | 9,156 / 0 | 9,156 / 0 | 9,156 / 0 | none | 9 | PASS |
| zookeeper | 3,951 | 11,853 / 0 | 11,853 / 0 | 11,853 / 0 | none | 9 | PASS |

## Findings before the fixes, and the fixes

All operations completed under `base` and `log`. Under `enforce`, **Tomcat 11 failed 250 of 3,052
operations in every run**: the large static page `/docs/config/http.html` got no response. Log mode
showed these syscalls outside the profiles:

| Syscall | Apps | Made by | Why the analysis missed it | Fix |
|---|---|---|---|---|
| `copy_file_range` | Tomcat | JDK 25's libnio, which looks it up with `dlsym` and calls it through a pointer (the name is a string in libnio; it is not imported). Blocked, the file transfer fails. | no call graph shows a call through a pointer that `dlsym` returned | the C-library functions that an analysed library names in a string and does not import become start functions in that C library (latest set only) |
| `openat2`, `close_range`, `faccessat2` | all ten (`openat2`); Elasticsearch, OrientDB | runc 1.3.4's init | the latest set's runc whitelist predated runc 1.3.4 (118 entries) | the whitelist of the JDK 8 set: the four runc 1.3.4 syscalls and `fchown` (123) |
| `flock` | Tomcat, JRuby | JDK 21/25's libjvm, which imports it | JVM-internal code is not reachable from libjvm's JNI start functions | SysPart on the libraries libjvm imports from, starting from the imported functions |
| `sync_file_range` | Storm | RocksDB 8 | virtual calls through a vtable loaded via the GOT | vtable functions as start functions of C++ libraries (not libjvm) |

The fixes are the JDK 8 set's three, plus the `dlsym` rule. Profiles grow by 3 to 9 syscalls; Table III's totals:

| | Cassandra | ZooKeeper | Tomcat | Solr | Groovy | OrientDB | Jetty | Elasticsearch | Storm | JRuby |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 230 | 191 | 174 | 221 | 187 | 175 | 186 | 199 | 202 | 182 |
| fixed | 233 | 196 | 180 | 224 | 191 | 183 | 191 | 208 | 207 | 187 |

## Files

| File | Purpose |
|---|---|
| `run_validation.py` | the harness (the JDK 8 one with the newer images, readiness checks and workloads) |
| `make_table.py`, `extract_audit_records.py` | summary table; raw audit records for runs that did not save them |
| `scripts/` | the Groovy and JRuby workloads |
| `control/` | the positive control and its results (`result_current.json` also lists the JRuby profile's real misses, `flock` and `openat2`) |
| `profiles/`, `results/`, `logs/` | the profiles tested and every run |
