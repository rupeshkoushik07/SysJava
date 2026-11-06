# Unmapped native methods: missing-library investigation (latest containers)

Date: 2026-11-05. Scope: stage 5 (native mapping) of the latest-versions run,
`Final_results_latest_versions/` and `workspaces/` (code at 516fb46). Nothing in the
pipeline results was modified; everything here is a side experiment.

## Question

Stage 5 maps 3,862 of 4,426 native methods (87%) across the 7 targets that reached
it. Solr (61%), cassandra and zookeeper looked low. Are the unmapped methods caused
by native libraries missing from the container, and can they be mapped if the
library is supplied?

## Method

1. Split each target's unmapped methods into
   - **absent from the mapping file**: native methods in `native_methods.txt` the
     mapper never tries, which are natives for other operating systems;
   - **`NOT_FOUND_IN_LIBS`**: Linux natives whose symbol was not found in any
     scanned `.so`.
2. For each `NOT_FOUND` group, identify the native library it needs and search for
   it: the target's own JARs, `~/Prototype` (including the generic dumps
   `netty_libs*`, `hawtjni_libs`, `hadoop_*`, which hold none of the needed
   libraries), and **previous runs of the same container**
   (`~/Prototype/Final_results*/…/mapped_method_syscalls.txt` record the library path
   each method was mapped from).
3. Copy the found libraries into `unavailable_libs/<target>/` (provenance and
   sha256 in `PROVENANCE.tsv`), verify the version against the target's JAR, and
   rerun the pipeline's own mapper (`scripts/mapped_updated.py`, plus
   `extract_jni_bindings.py` for RegisterNatives tables) on **only the leftover
   methods**, with output in `unavailable_libs/<target>/mapping/`.

## Findings

| Target | Unmapped | Cause | Result with supplied library |
|---|---|---|---|
| solr_10.0.0 | 282 | 276 `io.netty.internal.tcnative.*`: solr 10 ships `netty-tcnative-boringssl-static-2.0.70.Final.jar` **without** the linux-x86_64 native, so the library is never loaded | **276/276 mapped** with the byte-identical 2.0.70 linux-x86_64 library from cassandra_5.0.6-bookworm (same file as Prototype `solr_slim`); 268 via RegisterNatives |
| cassandra_5.0.8 | 128 | 112 natives for other OSes (netty kqueue, sigar win32, NativeLibraryDarwin); 7 jffi `Foreign`, 6 Chronicle `NativeAffinity`, 1 OpenHFT `JNIClock`, 1 `Zstd.generateSequences`, 1 JDK | **0 mapped**: the jffi/zstd methods have no symbol in the exact-version libraries; the Chronicle/OpenHFT natives are not shipped (both fall back to Java) |
| orientdb_3.2.53 | 61 | 49 jffi `Foreign` methods, 4 Lucene `WindowsDirectory`, JDK | **0 mapped**: all 44 jffi methods are absent from `libjffi-1.2.so` (163 exports); the library was in the dataset all along |
| zookeeper_3.9.5 | 41 | 40 `org.jline.nativ.Kernel32*` (Windows console), 1 JDK | not applicable on Linux |
| groovy_5.0.6 | 42 | 38 `org.jline.nativ.Kernel32*` (Windows), 4 JDK | not applicable on Linux (an earlier note calling this a real gap was wrong) |

Previous runs of the same containers (cassandra_5.0.6-bookworm, cassandra_latest,
orientdb_3.2.19) report the same `NOT_FOUND` entries for the jffi, Chronicle and
OpenHFT methods, which confirms these are absent symbols, not a mapping bug.

JDK internals (`VM.getNanoTimeAdjustment`, `Continuation.doYield`, `Object.wait0`,
`MethodHandle.invokeExact`, a few JFR methods; ~20 in total) are implemented inside
the JVM (intrinsics or signature-polymorphic methods) and have no native function.

## Conclusion

Apart from solr's tcnative, every unmapped method is either for another OS, has no
native implementation in the shipped library version, or is a JVM intrinsic. The
mapping stage therefore misses essentially nothing that the container can execute.

Solr's tcnative natives can be mapped, but in solr_10.0.0 that library is **not
loaded at runtime** (it isn't in the captured libraries), so adding its syscalls to
solr's profile would over-approximate. Treat the mapping as a "what if the
container shipped it" result, not as a profile change.

## Files

- `PROVENANCE.tsv`: every supplied library, with sha256 and source.
- `<target>/leftover_methods.txt`: the methods re-mapped.
- `<target>/mapping/`: mapper output (`mapped_method_syscalls.txt`, logs, JNI bindings).

## Supplement analysis: solr_10.0.0 + tcnative (2026-11-05 ~13:00)

SysPart (June build, the same compute_syscalls_lowmem.sh as the pipeline, solr's own
symbolized LIBS for dependencies) on `libnetty_tcnative_linux_x86_64.so`, from **only**
the 276 newly mapped start functions (`solr_10.0.0/start_functions.txt`, all internal
RegisterNatives targets present in the library's `.symtab`).

- All 276 starts resolved. Call graph: 10,056 functions, 99 unnamed (all in
  libgcc_s, no symbols). Output: `solr_10.0.0/syspart/`.
- **45 reachable syscalls**, and **none of them is new** relative to solr's own
  results (125 syscalls from the 6 libraries analysed so far).
- So the missing tcnative library does not change solr's profile. The union is
  produced with `merge_supplement.py solr_10.0.0 solr_10.0.0/syspart/syscalls.txt`
  once solr's final `solr_10.0.0.txt` exists (expected +0).

## Mapping statistics after the supplement (9 of 10 targets)

See `mapping_statistics.txt`. 6,819 + 276 of 7,591 natives mapped (93%); excluding
natives that cannot run on Linux, 96.5%. Next candidates of the same kind: storm_2.8.8
(netty io_uring 62, shaded snappy 11, jansi/hawtjni 14, rocksdb 6 NOT_FOUND).

## storm_2.8.8 supplement (2026-11-05 ~13:00)

- jansi `libjansi.so` (from jline-2.14.6.jar, linux64): 9 `CLibrary*` natives now map. Not loaded at runtime.
- Shaded snappy (11) and netty io_uring (62): the libraries are present (snappy in storm-shaded-deps, io_uring already in the dataset), but storm relocates the Java classes to `org.apache.storm.shade.*` while the natives keep unshaded names (`Java_org_xerial_snappy_*`; io_uring registers under netty's own package). Storm itself cannot link them at runtime (epoll ships with the shaded name and is used instead), so they stay unmapped. A manual, prefix-stripped mapping would be possible but describes code that never runs.
- hawtjni `Callback` (7): its natives live in hawtjni's runtime library, which isn't shipped.
- rocksdb (7): absent from the shipped librocksdbjni (dead declarations).

## Comparison with paper Table III (latest containers)

See `paper_tableIII_vs_now.txt`.
- Five targets (cassandra, zookeeper, tomcat, groovy, jetty) match: same totals, resolved within ±3. The paper's total minus resolved equals platform + dead + intrinsic exactly (cassandra 1660-1533 = 127 = 111+15+1).
- solr: paper 714 resolved vs now 440. The paper's run had tcnative mapped (probably via the generic netty dumps the mapper no longer scans); with the exact tcnative 2.0.70 supplement we get 716.
- elasticsearch (paper 292 = today's unfixed stage-4 count; 363 with the clinit fix), storm (2668 -> 2802, fix) and orientdb (paper 108 vs 526 now, from a different capture) changed because of the analysis, not the mapping.
- Table II counts Platform/Intrinsic/Dead as resolved, while Table III excludes them from both resolved and Not Found. The paper should use one definition.

## Getting the supplements into the results (2026-11-05 ~13:10)

- solr_10.0.0 / tcnative: SysPart done (45 syscalls, 0 new so far).
- storm_2.8.8 / jansi: SysPart from the 9 newly mapped starts, in `storm_2.8.8/syspart_jansi/`.
- `merge_when_ready.sh` (log `merge_when_ready.log`) waits for each target's final
  `<target>.txt` profile and runs `merge_supplement.py`, writing
  `<target>/merged/<target>_with_supplement.{txt,json}` and `added_by_supplement.txt`.
  The pipeline results themselves are not modified.

## Default whitelist: set_tid_address added (user decision, 2026-11-05 ~13:25)

`set_tid_address` was added to `runc.txt` (EchoTrace/ and EchoTrace_latest/, one-line
change, alphabetical). An SCMP_ACT_LOG audit of zookeeper_3.9.5 showed it denied for
every process (bash, env, sed, grep, java, …). glibc calls it in its startup code
(`__libc_setup_tls` / `__libc_start_main`) before `main`, which SysPart never reaches
from the start functions. Denying it is harmless today, but it's a real syscall every
process makes, so it belongs with the runtime whitelist. (runc.txt can't hold comments:
`merge_all_syscalls.py` reads every non-empty line as a syscall name.)

## Previous-run comparison for orientdb and storm (2026-11-05 ~16:00)

Question (user): orientdb's 49 and storm's ~100 NOT_FOUND look too high; did earlier runs in
`~/Prototype` map them? Script and outputs: `prev_run_compare/` (`compare_prev.py`,
`orientdb.tsv`, `storm.tsv`, `storm_newly_mapped_by_june_mapper.tsv`).

**orientdb_3.2.53 (53 NOT_FOUND: 44 jffi `Foreign`, 5 Lucene `NativePosixUtil`, 3 JFR, 1 MethodHandle).**
- orientdb_3.2.19 (Final_results_echotrace): the same 49 are NOT_FOUND_IN_LIBS there too;
  orientdb_latest (June, smaller capture) never saw them. No previous run maps any of them.
- Root cause, verified: `jffi-1.3.9-native.jar` ships a Linux x86_64 `libjffi-1.2.so` dated
  **2012-09-13** (sha256 9c386102…, byte-identical to the container's). It exports 163
  `Java_com_kenai_jffi_Foreign_*` functions; jffi 1.3.9's `Foreign.class` declares 204 natives.
  The `*Checked` family, `newNativeMethod`, `compileNativeMethods`, `invokeArrayWithObjectsReturnObject`,
  etc. simply don't exist in the binary (calling them would throw UnsatisfiedLinkError). Not a mapping gap.
- Lucene `NativePosixUtil` needs `libNativePosixUtil.so` (lucene-misc), which is not shipped.

**storm_2.8.8 (103 NOT_FOUND with the current mapper).**
- storm_2.4.0 (old runs): 99 of them absent (older storm, different deps), 4 rocksdb mapped.
- storm_latest (June, `~/Prototype/Final_results/storm_latest`) mapped 66 of them.
- Reran the June mapper (`~/Prototype/mapped_updated.py`, copy + sha256 in
  `prev_run_compare/storm_june_mapper/`) on storm_2.8.8's own inputs: 41 NOT_FOUND instead of 103.
  The 62 extra mappings are:
  - 61 shaded io_uring natives (`org.apache.storm.shade.io.netty.channel.uring.{LinuxSocket,Native}`)
    via `add_relocated_netty_registered_aliases()` — present in the June mapper, absent from the
    EchoTrace_latest mapper. **But storm can't load that library:** `storm-shaded-deps-2.8.8.jar`
    renames epoll and tcnative to `liborg_apache_storm_shade_netty_*` (which netty's loader looks for
    with shaded classes), while io_uring and quiche keep the unshaded `libnetty_*` names. Netty's
    loader asks for `liborg_apache_storm_shade_netty_transport_native_io_uring42_x86_64.so`, which
    doesn't exist, so io_uring is unavailable and epoll is used. The library in LIBS_ was extracted
    from the jar by the pipeline, not captured at runtime. So the current mapper's NOT_FOUND is the
    correct runtime answer; the June alias over-maps.
  - 1 rocksdb `WBWIRocksIterator.refresh0Jni`: the library exports it only C++-mangled
    (`_Z46Java_org_rocksdb_WBWIRocksIterator_refresh0Jni...`, a missing `extern "C"` upstream), so the
    JVM can't link it. June mapper's loose match is a false hit.
- The remaining 41 are the categories already listed above (shaded snappy 11, hawtjni 7, jansi 9 via
  supplement, rocksdb dead 2, JDK intrinsics, quiche, macOS DNS).
- Side observation (not changed): the io_uring library still gets 244 SysPart starts in the current
  run (JNI_DYNAMIC aliases of netty's unix-common functions), i.e. a library storm can't load is analysed.
  That over-approximates storm's profile slightly; worth a look in the clinit rerun.
- Paper Table III (storm notfound 33) was likely produced with June-style aliasing.
- **Decision (user, ~16:10): drop storm's io_uring library from SysPart and the merge** (both start
  files, 84 + 160 starts). Sent to "Latest Containers Rerun" while storm stage 7 was at [8/22], before
  it reached them. Same reasoning would apply to `libnetty_quiche42_linux_x86_64` (also unshaded in
  storm-shaded-deps); user decided to KEEP it (~16:15).

## Manual mapping from previous runs (2026-11-05 ~23:40)

`prev_run_compare/search_all_prev.py` looked up every NOT_FOUND native of storm, orientdb,
elasticsearch and jruby in all 141 `mapped_method_syscalls.txt` files under ~/Prototype and
~/Tutorial (`hits_<target>.tsv`). Found and supplied (provenance in PROVENANCE.tsv):
- orientdb_3.2.53: 37 jffi `Foreign` natives from jffi **1.3.11**'s libjffi-1.2.so (cassandra_5.0.6
  image, symbolized). orientdb ships jffi 1.3.9, whose linux library is a 2012 build without them,
  so this is a newer-version library than the image's. 5 Lucene `NativePosixUtil` natives from
  libNativePosixUtil.so (Lucene ships it only as source; the same build previous runs used for
  solr 8.7.0 / ES 7.5.2; a build from Lucene 8.7.0 source lacks posix_fadvise).
- elasticsearch_7.1.0: the same 5 NativePosixUtil natives.
- storm_2.8.8: of 75 found elsewhere, 61 are the shaded io_uring natives (excluded: storm cannot load
  that library), 9 jansi (already supplied), 5 rocksdb from an older rocksdb build (storm 2.8.8's
  own library lacks them; not mixed in).
- jruby_10.1.0.0: none of its 13 found in any previous run.
SysPart from only the newly mapped starts (`run_supplement.sh`): orientdb jffi 33 + NativePosixUtil 34
syscalls, ES NativePosixUtil 40; none new against the current profiles (orientdb 172, ES 196).

## Remaining Not Found: search of every library on disk + classification (2026-11-05 ~23:55)

`notfound_search/`: `missing_natives.tsv` (135 natives with their JNI names), `unique_libs.txt` (3,195
unique .so under ~/Prototype, ~/Tutorial, ~/SysJava), `java_exports_index.tsv` (40,622 Java_* exports),
`matches.tsv` (only 4: storm's rocksdb failIfOptionsFileError natives, in an OLDER rocksdb build only).
Web search found nothing for the jffi/hawtjni/Chronicle/zstd/commons-daemon cases.
`classify.py` -> `classification.tsv` (every native, class + reason):
- mapped: 31 JDK-internal natives registered by the JVM itself (Unsafe/ScopedMemoryAccess/
  MethodHandleNatives/JFR registerNatives -> JVM_Register*/jfr_register_natives, Object.wait0 ->
  JVM_MonitorWait, VM.getNanoTimeAdjustment -> JVM_GetNanoTimeAdjustment, Perf.createLong); 17 of these
  functions are already in the target's libjvm call graph; ES JNACLibrary (5) -> libc (JNA direct mapping).
- platform: Class.getSuperclass, MethodHandle.invokeExact, Continuation.doYield (intrinsics), ES
  JNAKernel32Library (Windows), storm MacOSDnsServerAddressStreamProvider.
- not_found (reasons in the file): storm io_uring 62 (excluded, unloadable), shaded snappy 11, hawtjni 7,
  rocksdb 7, quiche 1; jffi dead declarations 7 each (cassandra/orientdb/jruby); Chronicle/OpenHFT 7 and
  zstd 1 (cassandra); commons-daemon jsvc 2 (tomcat); orientdb jfr_set_compressed_integers.
`binding_overrides.py` -> `<target>/binding_overrides.tsv`: unresolved JNA/JNR/FFM bindings; Linux jline
pty / jnr.unixsocket / RubyBasicSocket -> libc (mapped); Solaris/FreeBSD/macOS/Windows variants, FFM upcall
callbacks and the vDSO sched_getcpu call -> platform.
Table III: Not Found now cassandra 15, tomcat 2, orientdb 8, storm 88, jruby 7, others 0.
SysPart check of the not-yet-reached JVM starts (JVM_MonitorWait, JVM_GetNanoTimeAdjustment) on tomcat:
`tomcat_11.0.22/syspart_jvm_extra/`.

## storm_2.8.8: netty io_uring mapped manually (user decision, 2026-11-06 ~00:20)

The 62 shaded io_uring natives (`org.apache.storm.shade.io.netty.channel.uring.{LinuxSocket,Native}`) are
mapped to storm's own `libnetty_transport_native_io_uring42_x86_64.so` (netty 4.2.12, symbolized copy in
`storm_2.8.8/io_uring/`): 61 with the RegisterNatives symbols the June storm_latest run used, plus
`getPeerCredentials` -> `netty_io_uring_linuxsocket_getPeerCredentials`; all 62 verified in the library
(`io_uring_methods_symbols.tsv`, `start_functions_io_uring.txt`). SysPart from those starts: 48 syscalls
(`syspart_io_uring/`); new for storm: io_uring_setup, io_uring_enter, io_uring_register. Merged with the
jansi supplement: 193 -> 196 (`merged/`). Caveat kept: storm cannot load this library at runtime (it
registers unshaded io/netty/channel/uring/* classes), so the 3 syscalls are an over-approximation; the
pipeline profile (193, PASS) is unchanged. Table III now reports the merged profiles and counts all
manual mappings as resolved; supplement syscalls are part of Java Lib Syscalls.
- tomcat libjvm from JVM_MonitorWait + JVM_GetNanoTimeAdjustment: 104 syscalls, 0 new (unavailable_libs/tomcat_11.0.22/syspart_jvm_extra/).

## tomcat_11.0.22: jsvc built from the image's source (user decision, 2026-11-06 ~00:30)

`DaemonLoader.shutdown/failed` are registered by jsvc (`unix/native/java.c`, `RegisterNatives` with
`shutdown`/`failed`). The image ships only the source, `/usr/local/tomcat/bin/commons-daemon-native.tar.gz`
(commons-daemon 1.5.1). Built inside a throwaway `tomcat:11.0.22` container (apt gcc/make,
`CFLAGS="-g -O2" ./configure --with-java=/opt/java/openjdk && make`), logs in
`tomcat_11.0.22/jsvc_build/out/`. Mapped DaemonLoader.shutdown -> shutdown, .failed -> failed [REGISTERED].
SysPart on jsvc from those 2 starts: 39 syscalls (`syspart_jsvc/`), none new (merged profile 180). Tomcat
does not run jsvc in this container (catalina.sh), so this is a what-if mapping like storm's io_uring.
Tomcat Not Found 2 -> 0.

## Web/Maven search for the last Not Found natives (2026-11-06 ~00:45)

- Downloaded (data only, symbols inspected with nm) the newest zstd-jni (1.5.7-6) and jffi (1.3.14) from
  Maven Central: neither exports Zstd.generateSequences nor jffi Foreign newNativeMethod /
  compileNativeMethods / registerNativeMethods / ... -> declared in Java, never implemented natively.
- rocksdb fail_if_options_file_error: deprecated in RocksDB 9.0, later removed from the C++ library; storm's
  rocksdbjni still declares the Java natives (dead in its own version).
- Chronicle Enterprise NativeAffinity: native part of the commercial Enterprise edition, no public download.
- hawtjni Callback: hawtjni generates callback code into each project's own library; no standalone library.
- Shaded snappy/quiche: upstream libraries export unshaded JNI names; a matching library would have to be
  rebuilt with storm's package names (storm does not ship one).

## 2026-11-06: Cassandra 5.0.8 OpenHFT natives (libCEInternals.so built from source)
- Source: github.com/OpenHFT/Java-Thread-Affinity tag Java-Thread-Affinity-3.23.3 (commit 7556981), clone in
  _downloads/openhft-affinity-3.23.3; matches the image's affinity-3.23.3.jar (javap native declarations).
- Build (debian:bookworm, the image's base; g++ 12.2.0, openjdk-17 for `javac -h` headers), upstream Makefile:
  javac -proc:none -implicit:none -cp <image jars> -sourcepath src/main/java -h target/jni -d target/classes NativeAffinity.java JNIClock.java
  cd affinity/src/main/c && make JAVA_HOME=...
- Result: cassandra_5.0.8/openhft-affinity-3.23.3/libCEInternals.so exports 6 of the jar's 7 natives;
  NativeAffinity.rdtsc0 has no C implementation upstream (dead declaration).
- Mapping: notfound_search/classify.py (now idempotent) -> 6 lines in cassandra_5.0.8/mapping/.
- SysPart: one run, all 6 start functions: run_supplement.sh cassandra_5.0.8 <lib> start_functions_libCEInternals.so.txt syspart_libCEInternals
  -> 39 syscalls, all already in the 229-syscall profile (profile unchanged; earlier container PASS holds).
- Table: tables/tableIII_latest_rerun_2026-11-06_openhft.{tex,pdf}, built from the same results mix as _ffmfix
  (Final_results_latest_versions_clinit for orientdb/zookeeper). Only Cassandra changes: Resolved 1547->1553,
  JNI Static 786->792, Not Found 15->9.

## 2026-11-06 evening: Storm 2.8.8 mappings, runc dropped, final Table III
- Storm 2.8.8 (notfound_search/classify.py): 11 shaded snappy natives -> unshaded Java_org_xerial_snappy_* in the image's
  libsnappyjava (alias, like the pipeline's shaded quiche aliases); quiche_enable_debug_logging -> netty_quiche_enable_debug_logging;
  WBWIRocksIterator.refresh0Jni -> its C++-mangled symbol. Not Found 26 -> 13 (7 hawtjni, 6 rocksdb natives absent from rocksdbjni 10.10.1.1's library).
- One SysPart per library, full start list: scripts/manual_lib_rerun.sh storm_2.8.8 Final_results_latest_versions workspaces
  libsnappyjava_storm-shaded-deps-2.8.8.so libnetty_quiche42_linux_x86_64-4.2.12.Final.so librocksdbjni16624330668920755723.so
  -> snappy 0->34, quiche 42->42, rocksdb 61->61 syscalls; profile 193 unchanged. Previous results: Binary_Analysis_before_manual/.
- runc (user decision): merge_all_syscalls.py skips a runc binary result; runc.txt covers it. scripts/remerge_norunc.sh <t> <results_root> <ws_root>
  for the other 9 (logs tables/norunc_logs/); every profile unchanged, all PASS. Previous: Binary_Analysis_before_norunc/.
- Storm stage-11 check needs et-latest-zookeeper on et-latest-net (started in stage 1 only); started by hand, then
  WS_ROOT=<abs> RESULTS_ROOT=<abs> run_latest_target.sh storm_2.8.8 11 -> PASS (first check without ZooKeeper failed in baseline too).
- Final: tables/tableIII_latest_rerun_2026-11-06_final.{tex,pdf} (results mix: _clinit for orientdb/zookeeper);
  not-found list notfound_search/notfound_with_jars.tsv (37, rebuilt from classification.tsv) -> tables/notfound_natives_latest_2026-11-06_final.pdf.
