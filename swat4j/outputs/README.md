# SWAT4J on the ten JDK 8 Debian 10 images: outputs

Everything SWAT4J produced for Table `tab:results`, plus SysJava's allowlists for the same
images. To print the table from these files (Python 3 only, nothing is rerun):

```bash
python3 ../show_results.py .          # the table
python3 ../show_results.py . --sets   # also the syscalls only in SysJava / only in SWAT4J
```

Images: `zookeeper:3.4.14`, `tomcat:7.0`, `cassandra:3.0.29`, `jetty:9.4.51`, `storm:2.4.0`,
`orientdb:3.2.19`, `elasticsearch:7.5.2`, `solr:8.7.0`, `groovy:4.0.0`, `jruby:9.4.2.0`, each
as `<name>-jdk8-buster` (Debian 10, JDK 8; see `../../docker_images/`).

| Folder | What | Produced by |
|---|---|---|
| `static/native_methods/<app>.txt` | native methods SWAT4J's bytecode analysis (JTracer) found | `run_swat4j_host_out.sh` (SWAT4J unmodified, host OpenJDK 8u504) |
| `static/syscalls/<app>.txt` | SWAT4J static allowlist (`binary_analyser.py`) | same run |
| `static/logs/<image>.log.xz` | log of that run | same run |
| `mapping/<image>/` | SWAT4J's JNI mapping (`swat4j_mapping.py`) on SysJava's `native_methods.txt`: the native-resolution rows | `swat4j_mapping.py --libs-dir <image>/Dataset/LIBS_<image> --methods native_methods.txt` |
| `dynamic/<app>_result.txt` | SWAT4J dynamic allowlist: `strace -f -c` on Docker's containerd while the image starts, stopped at the ready line | `dynamic_swat4j_jdk8deb.sh <app>` |
| `dynamic/<app>_strace.txt`, `<app>.log` | raw `strace -c` table, container log | same |
| `dynamic/timing.csv`, `dynamic_runs.tsv` | one row per try; a try is clean when no other container started during it (`other_container_starts=none`). Only a clean last try is used | same |
| `sysjava/<app>.txt` | SysJava allowlist: `SCMP_ACT_ALLOW` names of its seccomp profile | SysJava pipeline (`../../2_swat4j_vs_sysjava/`) |
| `sysjava/SOURCE.tsv` | profile path and runtime-check result per image | same |

Rules: SWAT4J's allowlist is static ∪ dynamic. `ausyscall` names syscalls 17/18 `pread`/`pwrite`
where Docker uses `pread64`/`pwrite64`; the two are aliased. Nothing else is filtered.

Cassandra and OrientDB ship native libraries inside JARs (Netty epoll, JFFI). Their static runs use
datasets that include those recovered libraries.

Elasticsearch: SysPart could not analyse the ML `controller` binary. Its syscalls come from the
functions it imports (`sysjava/elasticsearch_ml_component_imports.md`).
