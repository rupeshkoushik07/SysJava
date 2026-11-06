# 1. Latest containers (Table `tab:latest`)

SysJava on newer releases of the studied applications (JDK 8 to 25).

| Image (folder) | Docker tag | JDK | OS |
|---|---|---|---|
| `cassandra_5.0.8` | `cassandra:5.0.8` | 17 | Debian 12 |
| `zookeeper_3.9.5` | `zookeeper:3.9.5` | 17 | Ubuntu 22.04 |
| `tomcat_11.0.22` | `tomcat:11.0` (as `tomcat:11.0.22`) | 25 | Ubuntu 24.04 |
| `solr_10.0.0` | `solr:10.0.0` | 25 | Ubuntu 24.04 |
| `groovy_5.0.6` | `groovy:5.0.6` | 21 | Ubuntu 24.04 |
| `orientdb_3.2.53` | `orientdb:latest` (as `orientdb:3.2.53`) | 8 | Ubuntu 26.04 |
| `jetty_12.1.10` | `jetty:12.1.10` | 25 | Ubuntu 26.04 |
| `elasticsearch_7.1.0` | `docker.elastic.co/elasticsearch/elasticsearch:7.1.0` | 12 | CentOS 7 |
| `storm_2.8.8` | `storm:latest` (as `storm:2.8.8`), with `zookeeper:3.9.5` | 17 | Ubuntu 26.04 |
| `jruby_10.1.0.0` | `jruby:10.1.0.0` | 21 | Ubuntu 24.04 |

Digests: `../docker_images/IMAGES.md`.

## Files

* `results/<image>/`: one result per image (layout in the top-level README).
* `STATUS.md`: whether each image runs under its profile.
* `tables/`: Table III as in the paper (`tableIII_latest_rerun_*.tex`, `.pdf`), the
  remaining not-found natives with their reasons (`notfound_natives_latest_*.pdf`),
  and the rows computed from `results/` (`table.md`).
* `scripts/`: the pipeline scripts; `runc.txt`: the runtime syscall set.

## Reproduce

```bash
../whitelist.sh zookeeper_3.9.5     # allowlist without SysPart, minutes
TABLE_ONLY=1 ./reproduce.sh         # table from the shipped results
./reproduce.sh                      # full rerun of all 10 images (needs ../setup.sh)
./reproduce.sh tomcat_11.0.22       # one image
```

## Notes

* Stage 4 of ZooKeeper, OrientDB, Elasticsearch, Storm and JRuby used `echotrace/`
  (`52628c4`, with the `<clinit>` fix); the other five used `echotrace_516fb46/`.
  `whitelist.sh` picks the matching one.
* On glibc ≥ 2.41 (OrientDB, Jetty, Storm), `scripts/cancel_syscall_sites.py`
  recovers syscalls made through `__syscall_cancel`.
* Each `ADDED_first_start_binaries.md` explains executables that were added by
  hand because the capture missed them.
