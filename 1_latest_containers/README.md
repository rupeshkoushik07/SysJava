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
* `tables/`: Table III (`tableIII_latest.tex`, `.pdf`) and the mapping counts it
  reads (`mapping_audit_per_app.csv`). No native is left Not Found.
  `TABLE_ONLY=1 ./reproduce.sh` regenerates Table III from `results/` and compares it.
* `manual_mapping/`: the other inputs of Table III: natives whose library the image
  does not ship, mapped after supplying the library (`PROVENANCE.tsv`, `<image>/mapping/`),
  natives no library implements (`<image>/dead_rta.txt`), and the classification
  rules (`notfound_search/classify_rta.py`).
* `scripts/`: the pipeline scripts; `runc.txt`: the runtime syscall set.

## Reproduce

```bash
python3 ../generate_syscalls.py zookeeper_3.9.5   # syscalls and profile from SysPart's call graphs, minutes
TABLE_ONLY=1 ./reproduce.sh         # Table III from the shipped results
./reproduce.sh                      # full rerun of all 10 images (needs ../setup.sh)
./reproduce.sh tomcat_11.0.22       # one image
```

## Notes

* Stage 4 of all ten used `../echotrace/` (`89bf135`): native methods are found on an
  RTA call graph (virtual and interface calls dispatched to the overrides of every
  class instantiated in reachable code), including class initialisers.
* Storm's Total Syscalls in Table III (202) is its pipeline profile (200) plus the
  syscalls of the supplied netty io_uring library (`io_uring_setup`, `io_uring_enter`,
  `io_uring_register`), minus `sync`, which only false FFM hits reach. That profile and
  its PASS check are in `manual_mapping/storm_2.8.8/merged_rta/`.
* On glibc ≥ 2.41 (OrientDB, Jetty, Storm), `scripts/cancel_syscall_sites.py`
  recovers syscalls made through `__syscall_cancel`.
* Each `ADDED_first_start_binaries.md` explains executables that were added by
  hand because the capture missed them.
