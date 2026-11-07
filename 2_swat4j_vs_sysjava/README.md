# 2. SWAT4J vs SysJava on JDK 8 (Table `tab:results`)

SWAT4J supports only JDK 8, so this comparison uses ten JDK 8 images, all rebuilt
on Debian 10 (buster) with Eclipse Temurin 8u504-b01. Each keeps its official
application layout and start command; only the OS and JDK change. Dockerfiles,
build script and image IDs: [`../docker_images/`](../docker_images/README.md).

| Image (folder) | Started as |
|---|---|
| `zookeeper_3.4.14-jdk8-buster` | default |
| `tomcat_7.0-jdk8-buster` | default |
| `cassandra_3.0.29-jdk8-buster` | default |
| `jetty_9.4.51-jdk8-buster` | default |
| `storm_2.4.0-jdk8-buster` | `storm nimbus`, with `zookeeper:3.7` |
| `orientdb_3.2.19-jdk8-buster` | default |
| `elasticsearch_7.5.2-jdk8-buster` | `ES_JAVA_OPTS=-Xms1g -Xmx1g` |
| `solr_8.7.0-jdk8-buster` | default |
| `groovy_4.0.0-jdk8-buster` | `groovysh` |
| `jruby_9.4.2.0-jdk8-buster` | `irb` (ready after 30 s; it prints no ready line) |

## Files

* `../swat4j/outputs/`: SWAT4J's static and dynamic allowlists and SysJava's
  allowlists for the ten images; `python3 ../swat4j/show_results.py ../swat4j/outputs`
  prints the table.
* `tables/tab_results.{tex,pdf,md}`: the table; `tables/mapping_audit_per_app.csv`:
  the native-method mapping counts it reads (SysJava and SWAT4J);
  `tables/storm_no_false_ffm/`: Storm under its profile without `sync` (172 syscalls,
  PASS), the only syscall of false FFM hits.
* `sysjava_results/<image>/`: full SysJava results. All ten pass under their profiles.
  Stage 4 used `../echotrace/` (`89bf135`, as for Table III), which follows virtual and
  interface calls to the overrides of every class instantiated in reachable code (RTA).
* `manual_mapping/`: natives whose library the image does not ship, mapped to the
  released library (`PROVENANCE.tsv`, `<image>/mapping/`), and the rules for the rest
  (`jdk8_notfound_search/classify_jdk8.py`).
* `scripts/`: the pipeline scripts; `runc.txt` + `runc_host_1.3.4_additions.txt`: the runtime syscall set.

## Reproduce

```bash
TABLE_ONLY=1 ./reproduce.sh                # the tables from the shipped outputs
./reproduce.sh                             # SysJava + SWAT4J on all 10 (needs ../setup.sh)
./reproduce.sh jetty_9.4.51-jdk8-buster    # one image
SKIP_SYSJAVA=1 ./reproduce.sh              # SWAT4J only
SKIP_SWAT4J=1 ./reproduce.sh               # SysJava only
```

SWAT4J (commit `6929d66`) is run unmodified; its dynamic analysis traces
containerd with `strace`, so it needs sudo. See [`../swat4j/README.md`](../swat4j/README.md).

`runc_host_1.3.4_additions.txt` adds four syscalls issued by the host's runc
1.3.4 (`openat2`, `close_range`, `faccessat2`, `getppid`).
