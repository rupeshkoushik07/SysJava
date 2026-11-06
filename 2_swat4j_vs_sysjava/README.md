# 2. SWAT4J vs SysJava on JDK 8 (Table `tab:results`)

SWAT4J supports only JDK 8, so this comparison uses ten JDK 8 images. Results
are placeholders until the final runs finish.

| Image (folder) | Image | OS | JDK |
|---|---|---|---|
| `zookeeper_3.4.14` | official `zookeeper:3.4.14` | Debian 10 | 8u292 |
| `tomcat_7.0` | official `tomcat:7.0` | Debian 10 | 8u292 |
| `cassandra_3.0.29` | official `cassandra:3.0.29` | Ubuntu 22.04 | 8u402 |
| `orientdb_3.2.19` | official `orientdb:3.2.19` | Ubuntu 22.04 | 8u372 |
| `jruby_9.4.2.0` | official `jruby:9.4.2.0` | Ubuntu 20.04 | 8u372 |
| `storm_2.4.0-jdk8-buster` | rebuilt; run as `storm nimbus` with `zookeeper:3.7` | Debian 10 | Temurin 8u504 |
| `solr_8.7.0-jdk8-buster` | rebuilt | Debian 10 | Temurin 8u504 |
| `elasticsearch_7.5.2-jdk8-buster` | rebuilt | Debian 10 | Temurin 8u504 |
| `groovy_4.0.0-jdk8-buster` | rebuilt; run as `groovysh` | Debian 10 | Temurin 8u504 |
| `jetty_9.4.51-jdk8-buster` | rebuilt | Debian 10 | Temurin 8u504 |

The rebuilt images keep the official application layout and start command;
only the OS and JDK change (their official images ship JDK 11-17). Dockerfiles,
build script and digests: [`../docker_images/`](../docker_images/README.md).

## Files

* `sysjava_results/<image>/`: one SysJava result per image (layout in the top-level README).
* `../swat4j/outputs/`: SWAT4J allowlists, static and dynamic.
* `scripts/`: the pipeline scripts; `runc.txt` + `runc_host_1.3.4_additions.txt`: the runtime syscall set.

## Reproduce

```bash
../whitelist.sh jetty_9.4.51-jdk8-buster   # allowlist without SysPart, minutes
TABLE_ONLY=1 ./reproduce.sh                # table from the shipped results
./reproduce.sh                             # SysJava + SWAT4J on all 10 (needs ../setup.sh)
./reproduce.sh jetty_9.4.51-jdk8-buster    # one image
SKIP_SYSJAVA=1 ./reproduce.sh              # SWAT4J only
SKIP_SWAT4J=1 ./reproduce.sh               # SysJava only
```

The table goes to `tables_rerun/sysjava_vs_swat4j.md`: SysJava (A), SWAT4J
static + dynamic (B), A ∩ B, A ∖ B, B ∖ A.

SWAT4J (commit `6929d66`) is run unmodified, with no fixes or workarounds. Its
dynamic analysis traces containerd with `strace`, so it needs sudo. See
[`../swat4j/README.md`](../swat4j/README.md).

## Notes

* `runc_host_1.3.4_additions.txt` adds four syscalls issued by the host's runc
  1.3.4 (`openat2`, `close_range`, `faccessat2`, `getppid`).
* JRuby's `irb` prints no ready line, so it counts as ready after 30 s.
