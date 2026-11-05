# Which syscalls does SWAT4J's mapping miss? Per library, per binding mechanism

*How to rerun everything here: [../REPRODUCE.md](../REPRODUCE.md), section 4. Numbers are from
`out_mech_summary/` (generated 2026-11-05).*

## The question

A Java native method reaches the OS through some **binding mechanism**. The two tools recover
different mechanisms:

| Binding mechanism | Example | SysJava | SWAT4J |
|---|---|---|---|
| JNI static export | `Java_java_io_FileInputStream_open0` | ✔ | ✔, but drops names with JNI escapes (`_1`, `_00024`) |
| RegisterNatives in an app library | netty `JNI_OnLoad` tables | ✔ | partly, via a name heuristic |
| RegisterNatives in libjvm/libjava | `Unsafe_*`, `jfr_*`, `Perf_*`, `MHN_*` | ✔ (binary tables) | ✘ |
| JVM_ entry behind a JDK native | `Object.hashCode` → `JVM_IHashCode` | ✔ | ✔ (from OpenJDK source) |
| JNA | `Native.register(libc)`, `Native.load(Class)` | ✔ | ✘ |
| Panama FFM (JDK 22+) | `Linker.downcallHandle(SSL_do_handshake)` | ✔ | ✘ |

For each library SysPart analysed, we compare the syscalls reachable from SysJava's entry points
with those reachable from SWAT4J's. The call graph is identical for both; only the entry points
change.

## Short answer

> **Scope of "container level" below (added 2026-11-05).** Container-level counts here are the
> union over the analysed native libraries. The deployed profile also merges in the `java`
> binary, the libraries SysJava analysed without bindings, and a Docker runtime whitelist (117
> syscalls). Against the deployed profile, SWAT4J's mapping loses: Tomcat 11, nothing;
> Elasticsearch 7.1.0, `mlockall` only; Cassandra 3.0.29, `mlockall` and `munlockall`. Tomcat 11
> is worked through in full, with a no-binding arm, in [TOMCAT11_BINDING.md](TOMCAT11_BINDING.md).
> See REPRODUCE.md O12.

**SWAT4J's mapping misses syscalls in 3 of 14 containers under SysPart's own analysis, and in 7 of
14 once address-taken over-approximation is removed. The misses come from four concrete mapping
failures:**

1. **Libraries SWAT4J never enters (no binding support).** JNA into libc (Cassandra 3.0.29,
   Elasticsearch 7.1.0) and Panama FFM into libssl/libcrypto (Tomcat 11). SWAT4J's mapping gives
   these libraries **zero** entry points, so every syscall reached only through them is lost.
   Missing from the whole-container allowlist:
   * Elasticsearch: 6 (`mlockall`, `setrlimit`, `getrlimit`, `clock_getres`, `getdents`, `open`).
   * Cassandra 3.0.29: 3 (`mlockall`, `munlockall`, `fadvise64`).
   * Tomcat 11: 1 (`arch_prctl`).
2. **JNI names SWAT4J decodes wrongly.** SWAT4J cannot undo JNI's `_1` (for `_`) and `_00024`
   (for `$`) escapes. It silently drops `LZ4_compress*`, `XXH32_init`, `SnappyNative.rawCompress`,
   Lucene's `NativePosixUtil.posix_fadvise`, `SystemProps$Raw.platformProperties`, and so on.
   These happen to be the functions that allocate memory or do I/O. Under SysPart's full model,
   it costs Elasticsearch a 7th syscall (`fadvise64`, Lucene).
3. **RegisterNatives targets inside libjvm.** 1,104 entry points across 13 containers;
   SWAT4J recovers 10 of them. Under direct calls they add JFR's netlink socket syscalls
   (`socket`, `bind`, `sendto`, `recvmsg`, `getsockname`), `Perf.attach`'s `kill`/`lstat`, and
   `sched_setaffinity`.
4. **Wrong-library attribution does not explain any miss.** When a library was extracted
   twice, we credited SWAT4J by symbol name, so duplicate copies cost it nothing (see Method).

Under SysPart's full model, misses of types 2 and 3 vanish at container level. Any entry point
into a library reaches every address-taken function, so ~35–105 syscalls per library are
reachable regardless of which entry points exist. That is why the per-library and direct-call
views below are needed to see them.

## Method

* **Containers (14).**
  * 9 older images, mostly JDK 8 (6 with debug-symbol call graphs, 3 debug-symbol JDK 8
    rebuilds), plus Cassandra 5.0.6 (JDK 17).
  * 5 newer images on JDK 12–25: Tomcat 11.0.18, Elasticsearch 7.1.0, Solr slim, Groovy latest,
    ZooKeeper latest.
  * Exact paths and the excluded images (Jetty latest: truncated call graph; Cassandra/JRuby
    latest: incomplete) are in REPRODUCE.md §1.
* **SysJava's entry points** are SysPart's own start lists, plus the JNA/FFM start lists of
  `jna_ffi_analysis/`. Each entry point is labelled with the mechanism that produced it.
* **SWAT4J's entry points** come from running the unmodified SWAT4J mapper on each container's
  `native_methods.txt` and the container's own libraries. A library gets every symbol SWAT4J
  mapped that the library defines, *whichever file SWAT4J named*. This is generous to SWAT4J:
  * OrientDB extracts two identical `liblz4-java` copies.
  * Cassandra 5's runtime `libzstd-jni` differs from the jar copy SWAT4J scanned.

  Both would otherwise count as SWAT4J misses.
* **Two reachability modes, on the same graph:**
  * **full:** SysPart's model (`getsyscalls.py`), in which an indirect call reaches every
    address-taken function. Replaying SysJava's entry points reproduces SysPart's recorded
    `syscalls.txt` in every check: 78 + 32 library runs, with Tomcat 11's 5 libraries counted in
    both sets (`out_mech*/check.csv`).
  * **direct:** `INDIRECT` edges dropped. Not sound; it removes the address-taken blow-up, so
    each entry point's own contribution shows.
* **Excluded as a SysJava false positive:** Groovy 4.0.0 `libverify.so`. The FFM detector read
  Groovy's `VerifyClass` Ant task as a downcall (`out_mech_summary/excluded.csv`).

## Result 1: per container

*Coverage* = native methods mapped. *Entry pts* and *libs entered* count analysed libraries only.
*Lib-level pairs* = Σ over libraries of |syscalls reached in that library|. This is the
per-library view, before libraries are merged. *App union* = the container's library syscall set.
Each cell reads SysJava / SWAT4J.

### Older containers (JDK 8 unless noted)

| Container | Coverage SJ / SW (of N) | Entry pts | Libs entered | Lib-level pairs, full | Lib-level pairs, direct | App union, full | App union, direct | Missed by SWAT4J at app level |
|---|---|---|---|---|---|---|---|---|
| ZooKeeper 3.4.14 | 222 / 128 (234) | 219 / 128 | 5 / 5 | 376 / 376 | 258 / 253 | 80 / 80 | 66 / 62 | direct: bind getsockname recvmsg sendto |
| Tomcat 7.0 | 583 / 432 (612) | 544 / 432 | 8 / 8 | 547 / 547 | 368 / 362 | 111 / 111 | 95 / 94 | direct: sched_setaffinity |
| **Cassandra 3.0.29** | 609 / 464 (686) | 501 / 357 | **13 / 12** | 856 / 852 | 598 / 526 | **106 / 103** | 97 / 94 | **full + direct: fadvise64 mlockall munlockall** |
| OrientDB 3.2.19 | 458 / 322 (519) | 476 / 328 | 11 / 11 | 684 / 684 | 497 / 429 | 88 / 88 | 80 / 80 | — |
| JRuby 9.4.2.0 | 434 / 330 (448) | 216 / 213 | 3 / 3 | 182 / 182 | 136 / 136 | 75 / 75 | 55 / 55 | — |
| Cassandra 5.0.6 (JDK 17) | 1429 / 1232 (1635) | 1045 / 999 | 11 / 11 | 739 / 739 | 623 / 621 | 127 / 127 | 120 / 120 | — |
| Jetty 9.4.51 | 225 / 128 (229) | 264 / 128 | 4 / 4 | 305 / 305 | 226 / 221 | 80 / 80 | 66 / 62 | direct: bind getsockname recvmsg sendto |
| Groovy 4.0.0 | 291 / 186 (341) | 330 / 186 | 8 / 8 | 589 / 589 | 399 / 394 | 99 / 99 | 73 / 73 | — |
| Solr 8.7.0 | 322 / 210 (623) | 370 / 210 | 10 / 10 | 698 / 698 | 418 / 413 | 101 / 101 | 70 / 70 | — |

### Newer containers (JNA and FFM appear here)

| Container | JDK | Coverage SJ / SW (of N) | Entry pts | Libs entered | Lib-level pairs, full | Lib-level pairs, direct | App union, full | App union, direct | Missed by SWAT4J at app level |
|---|---|---|---|---|---|---|---|---|---|
| **Tomcat 11.0.18** | 25 | 258 / 199 (269) | **454 / 107** | **6 / 4** | **484 / 415** | **321 / 252** | **107 / 106** | 90 / 89 | **arch_prctl** |
| **Elasticsearch 7.1.0** | 12 | 271 / 201 (292) | 276 / 201 | **8 / 7** | **643 / 605** | **552 / 514** | **122 / 115** | 108 / 100 | **clock_getres fadvise64 getdents getrlimit mlockall open setrlimit** (+kill in direct) |
| Solr slim | 25 | 712 / 601 (722) | 678 / 555 | 7 / 7 | 654 / 654 | 417 / 417 | 122 / 122 | 110 / 110 | — |
| Groovy latest | 21 | 289 / 206 (331) | 281 / 198 | 7 / 7 | 595 / 595 | 361 / 360 | 117 / 117 | 96 / 95 | direct: poll |
| ZooKeeper latest | 17 | 690 / 625 (735) | 553 / 530 | 6 / 6 | 440 / 440 | 392 / 392 | 125 / 125 | 114 / 114 | — |

**Totals over the 14 containers:**

| Measure | SysJava | SWAT4J |
|---|---|---|
| Native methods mapped (of 7,676) | 6,793 | 5,264 |
| Entry points | 6,207 | 4,572 |
| Libraries entered (of 107) | 107 | 103 |
| (library, syscall) pairs, full | 7,792 | 7,681 |
| (library, syscall) pairs, direct | 5,566 | 5,290 |

Containers whose allowlist shrinks under SWAT4J's mapping: **3 (full), 7 (direct)**.

## Result 2: per binding mechanism (all 14 containers)

| Mechanism | Containers | Libraries | SysJava entry points | Also mapped by SWAT4J | Library-level syscalls SWAT4J's mapping does not reach (full / direct) |
|---|---|---|---|---|---|
| JNI static | 14 | 85 | 3,020 | 2,818 (93%) | 1 / 138 |
| RegisterNatives, app library | 3 | 6 | 1,341 | 1,290 | 0 / 0 |
| RegisterNatives, libjvm | 13 | 14 | 1,104 | **10 (1%)** | 0 / 28 |
| JVM_ entry | 11 | 11 | 433 | 382 | 0 / 0 |
| **JNA** | 3 | 4 | 19 | **0** | **41 / 41** |
| **Panama FFM** | 1 | 2 | 283 | **0** | **69 / 69** |
| Manual bridge (SIGAR) | 2 | 2 | 7 | 7 | 0 / 0 |

Reading it:

* **JNA and FFM are the mechanisms whose misses survive SysPart's full model.** SWAT4J has no
  entry point at all in those libraries. Every syscall they reach (41 + 69 library-level) is
  missing from that library's set, and 10 of them are missing from the containers' allowlists.
* **RegisterNatives in libjvm is SysJava's largest recovery** (1,104 entry points, 99% invisible
  to SWAT4J). Under the full model it adds nothing: libjvm is already entered through JVM_
  functions, and every RegisterNatives target is address-taken. Under direct calls it adds 28
  library-level syscalls.
* **JNI static** looks almost equal, but the 7% SWAT4J drops are not random (Result 3c). They add
  138 library-level syscalls under direct calls.

## Result 3: the cases, with call paths

All paths come from the SysPart graphs and use direct edges only. Each is regenerated with
`trace_path.py <lib_dir> <entry> <syscall> --direct`.

### 3a. Panama FFM: Tomcat 11.0.18 (JDK 25), libssl and libcrypto

`tomcat-coyote-ffm.jar` makes 375 `downcallHandle` bindings into OpenSSL (SysJava resolves 301;
`jna_ffi_analysis/resolved_bindings.tsv`). SWAT4J's mapping has no entry point in either
library.

| Library | SysJava (FFM) entry points | SWAT4J | Syscalls SysJava / SWAT4J |
|---|---|---|---|
| libssl.so.3 | 182 | 0 | 35 / 0 |
| libcrypto.so.3 | 101 | 0 | 34 / 0 |

At container level this costs `arch_prctl`, which is in Tomcat 11's final profile:

```
SSL_do_handshake -[DIRECT]-> (static helper 0x33af0) -[DIRECT]-> ASYNC_start_job
  -[DIRECT]-> swapcontext -[syscall]-> arch_prctl
```

Runtime evidence: the sysdig capture shows the `java` process opening
`/lib/x86_64-linux-gnu/libssl.so.3` and `libcrypto.so.3`.

Caveat: this path is taken only when OpenSSL's async mode is in use.

### 3b. JNA: Elasticsearch 7.1.0 and Cassandra 3.0.29, libc

**Elasticsearch.** `org.elasticsearch.bootstrap.JNACLibrary` direct-maps `geteuid`, `getrlimit`,
`setrlimit`, `mlockall` and `strerror` from libc. SysJava gives libc 5 entry points; SWAT4J's
mapping gives none.

* Library level: libc reaches 37 syscalls from SysJava's entry points and 0 from SWAT4J's.
* Container level: 7 syscalls disappear from the allowlist, 6 because of JNA and 1 because of
  JNI decoding. All 7 are in SysJava's final Elasticsearch profile.

| Syscall | Comes from | Notes |
|---|---|---|
| `mlockall` | `JNACLibrary.mlockall` | runs only when `bootstrap.memory_lock: true` |
| `setrlimit`, `getrlimit` | `JNACLibrary.setrlimit/getrlimit` | bootstrap checks (max threads, max file size) |
| `getdents`, `open`, `clock_getres` | the JNA entry points (first found from `strerror`) inside glibc 2.17 | CentOS 7 glibc uses `open`, not `openat` |
| `fadvise64` | **not JNA**: Lucene `NativePosixUtil.posix_fadvise`, a JNI name with `_1` (3c) | libNativePosixUtil.so: 38 vs 37 |

**Cassandra 3.0.29.** `NativeLibraryLinux` does `Native.register(libc)`. Its `mlockall`,
`munlockall` and `posix_fadvise` reach their syscalls directly (`mlockall` → `mlockall`, …).
`CassandraDaemon.setup()` calls `tryMlockall()` on every start. The full write-up is in
[ENTRYPOINT_ABLATION.md](ENTRYPOINT_ABLATION.md).

### 3c. Wrong JNI decoding: lz4, snappy, Lucene, SystemProps

SWAT4J turns `Java_pkg_Class_method` into a dotted name and matches it against the Java method.
It does not undo JNI's escapes, so any method whose JNI name contains `_1` (a literal `_` in the
Java name) or `_00024` (a `$` in an inner-class name) is dropped:

| Container | Library | Java methods SWAT4J drops | Effect (direct calls) |
|---|---|---|---|
| Cassandra 3.0.29 | liblz4-java.so | `LZ4_compress*`, `LZ4_decompress*`, `XXH32_init/update/digest/free`, … (13 of 19) | 34 → 0 syscalls |
| Cassandra 3.0.29 | libsnappyjava.so | `rawCompress`, `rawUncompress`, `uncompressedLength`, … (overloads) | 34 → 0 |
| OrientDB 3.2.19 | liblz4-java (2 copies) | same as Cassandra | 34 → 0 each |
| Elasticsearch 7.1.0 | libNativePosixUtil.so | `posix_fadvise`, `posix_madvise`, `open_direct` | loses `fadvise64` (full and direct) |
| Groovy latest | libjava.so | `jdk.internal.util.SystemProps$Raw.platformProperties` (`_00024Raw`) | loses `poll` |

The functions SWAT4J does map in liblz4 (`XXH32`, `XXH64`, `XXH32BB`, `XXH64BB`, `init`) are
pure computation. The ones it drops are the ones that allocate:

```
Java_net_jpountz_lz4_LZ4JNI_LZ4_1compressHC -[DIRECT]-> LZ4_compressHC2_limitedOutput
  -[DIRECT]-> LZ4_freeHC -[DIRECT]-> free -[DIRECT]-> _int_free -[DIRECT]-> mmap -[syscall]-> mmap
```

### 3d. RegisterNatives inside libjvm: JFR and Perf

SWAT4J only knows `JVM_*` functions from OpenJDK source. The targets JDK classes bind with
`RegisterNatives` (`jfr_*`, `Perf_*`, `Unsafe_*`, `MHN_*`, `CONT_*`) have no `JVM_` name and no
`Java_` export, so SWAT4J cannot map them. Two examples with real syscall consequences (direct
calls):

```
jdk.jfr.internal.JVM.emitEvent  ->  jfr_emit_event
  -> JfrPeriodicEventSet::requestNetworkUtilization -> JfrNetworkUtilization::send_events
  -> JfrOSInterface::network_utilization -> NetworkPerformance::network_utilization
  -> getifaddrs -> __netlink_open -> socket                        (also bind, sendto, recvmsg, getsockname)

jdk.internal.perf.Perf.attach  ->  Perf_Attach -> PerfMemory::attach -> kill   (also lstat)
```

The JFR path appears in ZooKeeper 3.4.14, Jetty, Groovy 4.0.0, Solr 8.7.0 and Tomcat 7.0
(`jfr_create_jfr` → `sched_setaffinity`). The Perf path appears in Cassandra 5.0.6. Both run only
when the feature is used (a JFR recording; `jstat`/attach).

## Why most differences vanish under SysPart's full model

Inside a library SysPart has entered at all, an indirect call goes to every address-taken
function. libjvm alone reaches ~75–105 syscalls from *any* entry point. So:

* extra entry points in an already-entered library add nothing (types 2 and 3 above);
* only a library that one tool **never enters** (types 1: JNA and FFM) shows a difference.

This is a property of SysPart's analysis, not of the mapping. With a more precise
indirect-call analysis, e.g. resolving `JNIEnv` calls to JNI interface functions only, the
direct-mode column is the better guide to what the mapping is worth.

## Limitations and what we report against ourselves

* **SysJava false positive:** Groovy 4.0.0 `VerifyClass` → `libverify.so` (FFM detector).
  Excluded from all totals.
* **SysJava gap:** Elasticsearch's `SystemCallFilter` binds libc `prctl` and `syscall` through a
  JNA interface. SysJava detected them but could not resolve the library, so they were not
  analysed. (`prctl` and `seccomp` are still in the profile through other paths.)
* **Attribution errors that do not change these results:** 6 JNA libc functions (`close`,
  `open`, `fsync`, …) in Cassandra 3 were filed under libjvm, and in Cassandra 5 under libjava.
  These are the "libc bridges attributed to the wrong library" in RQ1_NATIVE_MAPPING.md. In
  Cassandra 3, `fsync` (libjvm, full and direct) comes from one of them.
* **Conditional paths:** FFM `arch_prctl` (OpenSSL async), JFR sockets (a recording is active),
  `Perf.attach` (attach tools), ES `mlockall` (`bootstrap.memory_lock`) are static paths. They
  run only under those configurations. Cassandra's `mlockall` runs on every start.
* **Not covered:**
  * Elasticsearch 7.5.2 and Storm 2.4.0 JDK 8 rebuilds (left out by decision);
  * JRuby latest's 39 JNR-FFI bindings (never run through SysPart);
  * Jetty latest (truncated libjvm graph).

  Three library folders were skipped for broken SysPart output (`out_mech_latest/skipped.csv`);
  each affects both arms equally.

## What to say in the paper

1. **Denominator and coverage:** SysJava maps 6,793 of 7,676 native methods in these 14
   containers; SWAT4J maps 5,264.
2. **Mapping matters most where SWAT4J has no binding model at all.** JNA and Panama FFM give
   SWAT4J zero entry points in the target library. The analysed libraries then lose syscalls
   the application really makes (deployed-profile losses are smaller; see the scope note
   under Short answer):
   * Elasticsearch 7.1.0: 6, incl. `mlockall`, `setrlimit` (plus `fadvise64` from point 3);
   * Cassandra 3.0.29: 3, incl. `mlockall` on every start;
   * Tomcat 11 FFM: 1.
3. **SWAT4J's JNI mapping is also wrong, not just incomplete.** It drops JNI names with `_1` and
   `_00024`, which removes exactly the allocating entry points of lz4 and snappy, and Lucene's
   `posix_fadvise`.
4. **SysPart's address-taken over-approximation hides the rest.** Say this openly. The per-library
   and direct-call numbers (5,566 vs 5,290 library-level syscalls; 7 of 14 containers differ)
   show what better mapping buys once indirect calls are resolved more precisely.

## Files

| File | Content |
|---|---|
| `mechanism_ablation.py` | the experiment (one container set per run) |
| `run_mechanism_ablation.sh` → `out_mech/` | older containers |
| `run_mechanism_latest.sh` → `out_mech_latest/` | newer containers |
| `summarize_mechanisms.py` → `out_mech_summary/` | the tables above |
| `out_mech_summary/per_container.csv` | Result 1 |
| `out_mech_summary/per_mechanism.csv` | Result 2 |
| `out_mech_summary/differing.csv` | every (container, library, mode) whose syscalls differ |
| `out_mech*/missed.csv` | each missed syscall: mechanism, example entry point, Java method |
| `trace_path.py` | the call paths in Result 3 |
