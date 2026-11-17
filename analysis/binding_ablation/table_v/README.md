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
| ZooKeeper 3.4.14 | 16 | 227 / 96 | 365 / 113 | 484 / 113 | 484 / 113 | 39,079 / 276 |
| Tomcat 7.0 | 19 | 588 / 116 | 670 / 128 | 792 / 128 | 792 / 128 | 40,117 / 276 |
| Cassandra 3.0.29 | 21 | 624 / 113 | 663 / 116 | 894 / 124 | 903 / 127 | 40,564 / 276 |
| Jetty 9.4.51 | 13 | 224 / 96 | 233 / 100 | 352 / 100 | 352 / 100 | 37,406 / 276 |
| Storm 2.4.0 | 19 | 1,483 / 121 | 1,459 / 122 | 1,835 / 133 | 1,835 / 133 | 48,135 / 277 |
| OrientDB 3.2.19 | 23 | 466 / 97 | 561 / 115 | 684 / 115 | 684 / 115 | 40,483 / 276 |
| Elasticsearch 7.5.2 | 19 | 351 / 99 | 483 / 116 | 604 / 116 | 611 / 118 | 39,637 / 276 |
| Solr 8.7.0 | 23 | 603 / 118 | 700 / 119 | 967 / 131 | 967 / 131 | 41,237 / 276 |
| Groovy 4.0.0 | 20 | 289 / 110 | 419 / 113 | 541 / 113 | 541 / 113 | 39,418 / 276 |
| JRuby 9.4.2.0 | 12 | 437 / 97 | 467 / 103 | 587 / 103 | 612 / 104 | 36,810 / 276 |

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

## JNI-static, JNI-full and SysJava binding columns (rebuilt from this artifact)

```bash
python3 jni_columns.py         # about 3 min; writes results/jni_columns.tsv and prints the checks
```

Same libraries, call graphs and libjvm imports as the SWAT4J column. A native's column is its Table II category:
its first mapper tag, read as Table II's generator reads it (`mapped_method_syscalls.txt`, then
`2_swat4j_vs_sysjava/manual_mapping/<image>/mapping/mapped_method_syscalls.txt`).

- **JNI-static = Table II's symbol lookup:** `[JNI]` (exported `Java_*` symbols: short, overloaded, escaped,
  including manual mappings to supplied libraries), `[JVM]` (JDK class tables to `JVM_*`), `[SIGAR_LIST_BRIDGE]`.
- **JNI-full = Table II's bound JNI:** plus explicit registration, `[JNI_DYNAMIC]` and `[REGISTERED]` (decoded
  `RegisterNatives` tables) and `[NETTY]`. Tomcat's 2 natives registered in the `jsvc` executable are counted as
  methods; `jsvc` is not one of the analysed libraries.
- **SysJava binding = JNI-full + JNA + JNR-FFI bindings that are bound** (library and function known, applicable on
  Linux): Cassandra +9 JNA, Elasticsearch +7 JNA, JRuby +25 JNR-FFI. JNA direct-mapped natives count only under JNA.
- **Checks (printed by the script):** JNI-static + explicit registration = JNI-full, JNI-full + JNA + JNR-FFI =
  SysJava binding, and the syscall sets nest (JNI-static within JNI-full within SysJava binding) in all ten images;
  the SysJava binding syscalls equal the paper's.
- **Why the columns are close:** in 7 images every `RegisterNatives` target is in `libjvm.so`, whose syscalls the
  other JNI libraries already reach: SysPart resolves an indirect call to every address-taken function, so most JNI
  libraries reach the same 75 syscalls. Explicit registration adds syscalls only through Netty (Cassandra +8, Storm
  +11, Solr +12: `epoll_*`, `accept4`, `eventfd2`, `splice`, ...); JNA adds Cassandra +3 (`fadvise64`, `mlockall`,
  `munlockall`) and Elasticsearch +2 (`mlockall`, `prctl`); JNR-FFI adds JRuby's `getpeername`.

## SysJava binding and No binding columns

[`results/java_base/`](results/java_base/summary.md): per image (`per_image.tsv`) and per library
(`per_library.tsv`), start functions and syscalls of both arms, with the checks (binding = Table IV's Java (base);
JRuby 104 = 103 + `getpeername`, reached only from its JNR-FFI functions). The no-binding runs are SysPart from
every function of each library file: `../jdk8_all/results/A/` (JNI libraries and `libjvm.so`) and
[`inputs/no_binding_runs/`](inputs/no_binding_runs) (the glibc libraries of libjvm's imports, JRuby's libc,
OrientDB's supplied libjffi). `../run_ablation.sh` reruns any of them (arm A, see `../jdk8_all/README.md`).
