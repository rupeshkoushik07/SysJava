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
| `static/native_methods/<app>.txt` | native methods SWAT4J's bytecode analysis (JTracer) found | `run_swat4j_host_out.sh` (SWAT4J unmodified, host OpenJDK 8u504), each image's LIBS folder plus SWAT4J's repository libraries `JNI_thirdparty/` (repository copy wins on a name clash, as in the original setup): `run_static_jdk8deb.sh` |
| `static/syscalls/<app>.txt` | SWAT4J static allowlist (`binary_analyser.py`) on each image's own libraries: the image's JDK and its dependencies as the image's loader resolves them | `image_libs/run_image_libs.sh` (after `image_libs/extract_rootfs.sh`), on the native methods above |
| `static/logs/<image>.log.xz`, `<image>.ldd.xz` | log of that run, every library lookup | `image_libs/run_image_libs.sh` |
| `mapping/<app>.tsv` | SWAT4J's own JNI mapping of the native methods its JTracer found (`static/native_methods/<app>.txt`): one row per method with the rule that mapped it (`Java_XXX`, `JVM_XXX`, `NETTY_HEURISTIC`) or `UNMAPPED`, the symbol and the library | `own_mapping_jdk8deb.sh` (`count_own_mapping.py`): builds SWAT4J's six name maps with its own unmodified functions and replays its `aggregate()` rules |
| `dynamic/<app>_result.txt` | SWAT4J dynamic allowlist: `strace -f -c` on Docker's containerd while the image starts, stopped at the ready line | `dynamic_swat4j_jdk8deb.sh <app>` |
| `dynamic/<app>_strace.txt`, `<app>.log` | raw `strace -c` table, container log | same |
| `dynamic/timing.csv`, `dynamic_runs.tsv` | one row per try; a try is clean when no other container started during it (`other_container_starts=none`). Only a clean last try is used | same |
| `sysjava/<app>.txt` | SysJava allowlist: `SCMP_ACT_ALLOW` names of its seccomp profile | SysJava pipeline (`../../2_swat4j_vs_sysjava/`) |
| `sysjava/SOURCE.tsv` | profile path and runtime-check result per image | same |

Rules: SWAT4J's allowlist is static ∪ dynamic. `ausyscall` names syscalls 17/18 `pread`/`pwrite`
where Docker uses `pread64`/`pwrite64`; the two are aliased. Nothing else is filtered.

SWAT4J reads four of its six repository libraries (Netty epoll, JFFI, Tomcat Native, 32-bit Sigar) by fixed
file name; Hadoop and RocksDB are never read. The 32-bit Sigar brings 32-bit libc code into Cassandra's
static analysis, whose i386 syscall numbers are named with the x86-64 table. SWAT4J's static list can
differ between identical runs by fchdir, ftruncate and kill.

Elasticsearch: SysPart could not analyse the ML `controller` binary. Its syscalls come from the
functions it imports (`sysjava/elasticsearch_ml_component_imports.md`).

Storm: `sysjava/storm.txt` leaves out `sync`, which comes only from FFM calls SysJava's detector inferred from
Clojure class names (JDK 8 has no FFM API); Storm runs under the resulting 172-syscall profile.
