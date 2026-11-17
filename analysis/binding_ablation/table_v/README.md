# Table V: binding ablation

Table V of the paper (`tab:ablation`, [`table_v.tex`](table_v.tex), [`table_v.pdf`](table_v.pdf)): the
syscalls SysPart reaches in the same native libraries of the ten JDK 8 images (Table II) when it starts from

- **SWAT4J binding**: the native methods SWAT4J identifies (its own JTracer list), mapped to native targets by
  SysJava's mapping;
- **SysJava (JNI-static)**: the targets SysJava recovers by JNI symbol lookup only (`Java_*` names);
- **SysJava (JNI-full)**: JNI symbol lookup and `RegisterNatives`;
- **SysJava binding**: every native target SysJava recovers (Table IV's *Java (base)*);
- **No binding**: every function of each library, `libc` included.

Methods / Syscalls per column (No binding: entry functions / syscalls):

| Container | Libs | SWAT4J binding | JNI-static | JNI-full | SysJava binding | No binding |
|---|---:|---:|---:|---:|---:|---:|
| ZooKeeper 3.4.14 | 16 | 227 / 96 | 321 / 113 | 484 / 113 | 484 / 113 | 39,079 / 276 |
| Tomcat 7.0 | 19 | 588 / 116 | 623 / 128 | 790 / 128 | 792 / 128 | 40,117 / 276 |
| Cassandra 3.0.29 | 21 | 624 / 113 | 613 / 116 | 889 / 124 | 914 / 127 | 40,564 / 276 |
| Jetty 9.4.51 | 13 | 224 / 96 | 187 / 100 | 352 / 100 | 352 / 100 | 37,406 / 276 |
| Storm 2.4.0 | 19 | 1,483 / 121 | 1,412 / 122 | 1,835 / 133 | 1,835 / 133 | 48,135 / 277 |
| OrientDB 3.2.19 | 23 | 466 / 97 | 516 / 115 | 684 / 115 | 684 / 115 | 40,483 / 276 |
| Elasticsearch 7.5.2 | 19 | 351 / 99 | 436 / 116 | 604 / 116 | 625 / 118 | 39,637 / 276 |
| Solr 8.7.0 | 23 | 603 / 118 | 653 / 119 | 967 / 131 | 967 / 131 | 41,237 / 276 |
| Groovy 4.0.0 | 20 | 289 / 110 | 367 / 113 | 541 / 113 | 541 / 113 | 39,418 / 276 |
| JRuby 9.4.2.0 | 12 | 437 / 97 | 422 / 103 | 587 / 103 | 620 / 104 | 36,810 / 276 |

## SWAT4J binding column (rebuilt from this artifact)

```bash
python3 swat4j_binding.py      # about 2 min, 4 GB of memory; writes results/swat4j_binding.tsv
```

- **Natives:** SWAT4J's list, `swat4j/outputs/static/native_methods/<app>.txt`.
- **Mapping:** SysJava's, `2_swat4j_vs_sysjava/sysjava_results/<image>/Bytecode_Analysis/outputs_<image>/`
  (`mapped_method_syscalls.txt`, `manual_mapped_method_syscalls.txt`, `jna_hits.txt`). *Methods* counts the
  SWAT4J-listed natives SysJava maps to a native target.
- **Syscalls:** the shipped SysPart call graph of each library (`.../syscalls_output_<image>/<lib>/callgraph.json.gz`,
  including `libjvm.so`, and the JNA-bound libraries in `jna_ffi_analysis/`) is walked from those targets.
  libjvm's imported libraries (`extra_components/jvm_internal_imports/`) are the JVM itself and are counted in both
  binding columns.
- **Check:** the same script re-walks every library from SysJava's full start lists and compares with the SysJava
  binding column (`rewalked_binding_syscalls` vs `paper_binding_syscalls` in the tsv). JRuby's JNR-FFI libc
  functions (`inputs/jruby_jnr/`) and OrientDB's supplied `libjffi-1.2.so`
  (`2_swat4j_vs_sysjava/manual_mapping/orientdb_3.2.19-jdk8-buster/`) are two binding runs the pipeline does not
  make; they are part of the SysJava binding column.
- **SWAT4J's syscalls are a subset of SysJava's in every image.** The difference (`only_binding` in the tsv) comes
  from natives SWAT4J does not identify, e.g. `libnio.so` (`fsync`, `fdatasync`, `sendfile`, `pwrite64`),
  `libawt_xawt.so` (`getresuid`, `select`, `umask`, `flock`), and Elasticsearch's JNA call to `prctl`.
- **Walking a call graph vs a new SysPart run:** a graph built from more start functions can hold extra
  indirect-call targets. SysPart run from only SWAT4J's start functions (ZooKeeper `libjava.so`, `libnet.so`,
  `libzip.so`) gives the same syscalls except `setpriority` in `libjava.so`, which libjvm's imports add anyway.

## JNI-static and JNI-full columns (rebuilt from this artifact)

```bash
python3 jni_columns.py         # about 3 min; writes results/jni_columns.tsv
```

Same libraries, call graphs and libjvm imports as the SWAT4J column; only the start functions differ, chosen by the
mapper tag of each mapping (`mapped_method_syscalls.txt`, `manual_mapped_method_syscalls.txt`):

- **JNI-static:** `[JNI]`, i.e. exported `Java_*` symbols in their short, overloaded (`__` + argument types) and
  escaped (`_1`, `_00024`) forms, including manual mappings to supplied libraries.
- **JNI-full:** JNI-static plus `RegisterNatives`: `[JNI_DYNAMIC]` and `[REGISTERED]` (decoded registration tables),
  `[JVM]` (JDK class tables to `JVM_*`), `[NETTY]`.
- **Neither:** JNA, JNR-FFI, FFM, and Cassandra's `[DIRECT_LIBC_BRIDGE]` (9) and `[SIGAR_LIST_BRIDGE]` (5) mappings.
  The SysJava binding column adds them, and Tomcat's 2 natives in the `jsvc` executable.
- **Methods check:** JNI-full equals Table II's symbol lookup + explicit registration except Tomcat (790 vs 792, the
  `jsvc` natives) and Cassandra (889 vs 894, the Sigar list bridges); JNI-static equals Table II's static + partial.
- **Why JNI-static and JNI-full tie in 7 images:** there every `RegisterNatives` target is in `libjvm.so`, and the 76
  syscalls libjvm reaches are already reached through the other JNI libraries. SysPart resolves an indirect call to
  every address-taken function (the JNIEnv table alone makes every JNI library reach libjvm, libc and libpthread
  code), so most JNI libraries reach the same 75 syscalls. `RegisterNatives` adds syscalls only through Netty
  (Cassandra +8, Storm +11, Solr +12: `epoll_*`, `accept4`, `eventfd2`, `splice`, ...); JNA adds Cassandra +3 and
  Elasticsearch +2, JNR-FFI adds JRuby's `getpeername`.

## SysJava binding and No binding columns

[`results/java_base/`](results/java_base/summary.md): per image (`per_image.tsv`) and per library
(`per_library.tsv`), start functions and syscalls of both arms, with the checks (binding = Table IV's Java (base);
JRuby 104 = 103 + `getpeername`, reached only from its JNR-FFI functions). The no-binding runs are SysPart from
every function of each library file: `../jdk8_all/results/A/` (JNI libraries and `libjvm.so`) and
[`inputs/no_binding_runs/`](inputs/no_binding_runs) (the glibc libraries of libjvm's imports, JRuby's libc,
OrientDB's supplied libjffi). `../run_ablation.sh` reruns any of them (arm A, see `../jdk8_all/README.md`).
