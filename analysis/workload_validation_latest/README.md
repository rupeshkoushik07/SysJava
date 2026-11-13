# Workload validation of the latest-version profiles (Table III)

The same validation as [`../workload_validation/`](../workload_validation/README.md) (the JDK 8 images), on
the ten newer images of `1_latest_containers/` (JDK 8 to 25). Each image runs a real workload in three
modes, three times each (90 runs):

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

The profiles are the published ones (`profiles/<image>.json`, Table III's Total Syscalls). Storm's is the
Table III one: the pipeline profile, plus the supplied io_uring library's syscalls, minus the false-FFM
`sync` (207).

## Reproduce

```bash
cd analysis/workload_validation_latest
python3 -c "import run_validation as r; r.prepare()"    # inputs once, before parallel runs
python3 control/positive_control.py control/result_check.json   # "passed": true
export WLV_RESULTS=results_rerun                        # profiles/ is used by default
python3 run_validation.py tomcat jetty storm --reps 3 &
python3 run_validation.py elasticsearch solr cassandra --reps 3 &
python3 run_validation.py zookeeper orientdb groovy jruby --reps 3 &
wait
python3 make_table.py                                   # -> $WLV_RESULTS/table.md
```

## Results (`results/`, 2026-11-11)

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

All ten pass: every operation completes under `enforce`, no operation fails, and no log run records a
syscall outside the profile. Every run has `<mode>_<rep>.json`, `.container.log`, and for log mode
`.audit.log`, the raw audit records. `logs/` has the console output. The positive control
(`control/result.json`, raw records in `control/result.audit.log`) was run between the validation runs.

## Traced pass: the policy-validation table (`trace/`, 2026-11-13)

This is the same method as the JDK 8 pass (`../workload_validation/README.md`, "Traced pass"), with the
profiles in `profiles/`. `trace_validation.py` runs each workload once more under Docker's
default seccomp profile while sysdig (`--modern-bpf`) records every syscall of the container, from
start-up to the end of the workload:

- **performed**: the container's distinct syscalls, without runc's setup stages.
- **missing**: performed syscalls the profile does not allow. Storm uses its 207 profile.
- **permitted**: the profile's size, which is Table III's total.
- **new**: programs executed and `.so` files opened whose name is not in the image's dataset.
  Libraries that a JAR unpacks to `/tmp` under a random name are matched to the dataset copy:
  Netty tcnative, Netty epoll and snappy-java in Cassandra, listed in `loaded_under_other_name`.

| Container | Workload (ops) | Missing / performed / permitted | New binaries / libraries |
|---|---|---|---|
| Cassandra 5.0.8 | cqlsh + cassandra-stress (11) | 0 / 114 / 233 | 0 / 0 |
| Zookeeper 3.9.5 | zkCli + four-letter cmds (3,951) | 0 / 89 / 196 | 0 / 0 |
| Tomcat 11.0.22 | servlet/JSP GETs, POSTs, war deploy (3,052) | 0 / 93 / 180 | 0 / 0 |
| Solr 10.0.0 | collection, index, query, backup (194) | 0 / 104 / 224 | 0 / 1 |
| Groovy 5.0.6 | script: files, XML, zip, HTTP (46) | 0 / 89 / 191 | 0 / 0 |
| OrientDB 3.2.53 | REST CRUD, index, edges (1,808) | 0 / 85 / 183 | 0 / 0 |
| Jetty 12.1.10 | bare server: GETs, POSTs, keep-alive (3,075) | 0 / 89 / 191 | 2 / 0 |
| Elasticsearch 7.1.0 | bulk index, search, reindex (250) | 0 / 92 / 208 | 0 / 0 |
| Storm 2.8.8 | storm list + blobstore (35) | 0 / 105 / 207 | 0 / 0 |
| JRuby 10.1.0.0 | script: files, JSON, zlib, TCP (46) | 0 / 86 / 187 | 0 / 0 |

No application performs a syscall outside its profile. The three "new" files add no syscall outside the
profile either:
- **Jetty**: `/usr/bin/gnurm` (`rm`) and `/usr/lib/cargo/bin/coreutils/tee`. The image ships no
  `jetty.start`, so on every start its entrypoint runs `/generate-jetty-start.sh`, which calls `rm` and
  `tee`. The start-up capture did not record these two programs.
- **Solr**: `libattr.so.1`, opened by `cp`. `cp` is in the dataset, but this library it depends on is not.

```bash
cd analysis/workload_validation_latest
python3 trace_validation.py cassandra zookeeper tomcat solr groovy orientdb jetty elasticsearch storm jruby
python3 trace/make_table.py                  # -> trace/table.md, policy_validation_rows.tex
```
Needs sysdig with `--modern-bpf` and passwordless sudo for it. For the "new" column, set `WLV_DATASETS` to
a folder holding `<t>/Dataset/`, unpacked from `1_latest_containers/results/<t>/dataset/`.
`python3 trace_validation.py --analyse <apps>` recomputes the rows from the saved traces.

## Files

| File | Purpose |
|---|---|
| `run_validation.py` | the harness (the JDK 8 one with the newer images, readiness checks and workloads) |
| `make_table.py` | `table.md` from the run JSONs |
| `scripts/` | the Groovy and JRuby workloads |
| `control/` | the log-mode positive control and its result |
| `trace_validation.py`, `trace/` | the traced pass (policy-validation table) |
| `profiles/` | the profiles tested |
| `results/`, `logs/` | every validation run |
