# Does SysJava's native mapping change the syscall allowlist? (debug-symbol rerun)

## The question

SysJava maps far more Java native methods to C functions than SWAT4J (93.6% vs 69.4%). Does that
actually change which syscalls end up in the allowlist? The worry: SysPart over-approximates
indirect calls so heavily that any entry point reaches nearly everything, which would make
better mapping invisible.

## The experiment

For each library SysPart analysed, everything is held fixed (the binaries, and the call graph
built **with debug symbols**). Only the entry points change:

* **SysJava:** the functions SysJava's mapper gave SysPart for that library.
* **SWAT4J:** the functions SWAT4J's mapping assigns to the same library.

Reachable syscalls are recomputed with SysPart's own search (`getsyscalls_lowmem.py`). As a
check, replaying SysJava's entry points reproduces SysPart's recorded `syscalls.txt` exactly for
all 54 libraries.

Apps: the six with finished debug-symbol call graphs (ZooKeeper 3.4.14, Tomcat 7.0,
Cassandra 3.0.29, Cassandra 5.0.6, OrientDB 3.2.19, JRuby 9.4.2.0).

## Result

| App | Syscalls from SysJava's mapping | Syscalls from SWAT4J's mapping | Missed by SWAT4J's mapping |
|---|---|---|---|
| ZooKeeper 3.4.14 | 80 | 80 | — |
| Tomcat 7.0 | 111 | 111 | — |
| **Cassandra 3.0.29** | **106** | **103** | **`fadvise64`, `mlockall`, `munlockall`** |
| Cassandra 5.0.6 | 127 | 127 | — |
| OrientDB 3.2.19 | 88 | 88 | — |
| JRuby 9.4.2.0 | 80 | 80 | — |

Per library (`out/per_library.csv`), SysJava often has 3–4× more entry points. For example,
Cassandra's `libjvm.so` gets 150 SysJava entry points and 37 SWAT4J ones, yet the syscall sets
differ by at most one.

**So your suspicion is right: under SysPart's analysis, better mapping almost never adds
syscalls.** There is exactly one real case.

## The one real case: Cassandra 3.0.29

`org.apache.cassandra.utils.NativeLibraryLinux` binds libc functions directly with JNA:
`Native.register(NativeLibrary.getInstance("c"))`.

* SysJava's bytecode JNA detector finds all 9 bindings automatically and assigns them to
  `libc.so.6` (`Bytecode_Analysis/jna_directmap_hits.txt`).
* SWAT4J has no JNA support, so libc gets no entry points from it.

| Java method | libc function | syscall | Path in the debug-symbol call graph |
|---|---|---|---|
| `NativeLibraryLinux.mlockall` | `mlockall` | `mlockall` | `mlockall` → syscall |
| `NativeLibraryLinux.munlockall` | `munlockall` | `munlockall` | `munlockall` → syscall |
| `NativeLibraryLinux.posix_fadvise` | `posix_fadvise` | `fadvise64` | `posix_fadvise` → syscall |

These are real behaviour, not analysis noise:

* `CassandraDaemon.setup()` calls `NativeLibrary.tryMlockall()` on **every start** (bytecode of
  `apache-cassandra-3.0.29.jar`; it logs "JNA mlockall successful").
* `NativeLibrary.trySkipCache` issues `posix_fadvise` when dropping page cache for SSTables.
* SysJava's final allowlist (`Binary_Analysis/.../cassandra_3.0.29.json`) contains all three.
* None of SWAT4J's Cassandra allowlists contain any of them: static, combined and dynamic
  (`Tutorial/swat4j/comparison_published/details.md`).

A policy built from SWAT4J's mapping would deny `mlockall` at every Cassandra startup.
Cassandra catches the error and continues without locked memory, so the denial goes unnoticed in
a startup test.

## Why mapping rarely matters here (the over-approximation)

ZooKeeper's `libnet.so` has only 2 entry points, yet reaches 74 syscalls. The logged path to
`execve`:

```
Java_java_net_NetworkInterface_getByInetAddress0
  -[INDIRECT]-> VM_ReportJavaOutOfMemory::doit      (libjvm)
  -[DIRECT]->   os::fork_and_exec
  -[DIRECT]->   execve
```

and to `kill`:

```
Java_java_net_NetworkInterface_getByInetAddress0
  -[INDIRECT]-> Perf_Attach                         (a RegisterNatives target!)
  -[DIRECT]->   PerfMemory::attach -> mmap_attach_shared -> kill
```

Any JNI function that calls through the `JNIEnv` function table makes an indirect call. SysPart
resolves it to **every address-taken function** in libjvm. RegisterNatives targets are
address-taken by definition, because they are stored in `JNINativeMethod` tables. So as soon as a
library has *one* entry point, all the RegisterNatives targets SysJava recovers are already
reachable. Recovering them explicitly cannot add syscalls under this model.

Debug symbols do not change this (`Binary_Analysis` vs `Binary_Analysis_symbolized`):

* They remove 2–21 syscalls per library (e.g. `liblz4`, `libsnappy`, `libjffi`: 58 → 37).
* Every JDK library still lands at 73–105.
* App-level unions move by −14 to +5.

Cassandra 5.0.6 shows the same effect at library level. SWAT4J's mapping gives `libzstd-jni` and
`libsnappyjava` **zero** entry points, versus 53 and 37 syscalls from SysJava's. Yet the app total
is unchanged, because other libraries already reach those syscalls through address-taken calls.

## What this means for the paper

1. **Don't claim better mapping gives smaller or more complete policies in general.** Under
   SysPart's address-taken model it changes the allowlist in 1 of 6 apps.
2. **Claim what holds:** binding recovery decides *whether a library gets any entry point at all*.
   When a library is reached only through a mechanism SWAT4J doesn't model (JNA direct mapping
   here), SWAT4J's mapping loses syscalls the application really makes. Cassandra's `mlockall` is
   the concrete, verified example.
3. **State the reason for the null result openly.** It answers the ablation TODO ("separate
   analysis scope from binding recovery"): with indirect calls resolved to all address-taken
   functions, roots inside an already-rooted library are redundant. Better mapping would pay off
   with a more precise indirect-call analysis, e.g. resolving `JNIEnv` calls to the JNI interface
   functions rather than all of libjvm. That is a fair limitation and future-work point.

## Follow-up: per library, per binding mechanism

This container-level swap is extended in [MAPPING_PER_LIBRARY.md](MAPPING_PER_LIBRARY.md). It
covers 14 containers, including newer images with JNA and Panama FFM, splits SysJava's entry
points by binding mechanism, and adds a direct-call-only view. There:
* the Jetty 9.4.51 JDK 8 rebuild is again a null result (80 = 80, denominator 229);
* Elasticsearch 7.1.0 (JNA, 7 syscalls) and Tomcat 11 (FFM, 1 syscall) join Cassandra 3.0.29 as
  containers whose allowlist shrinks under SWAT4J's mapping.

How to rerun: [../REPRODUCE.md](../REPRODUCE.md).

* Library-level only. Syscalls from executables and the Docker runtime set are identical for both
  arms and left out.

## Files

* `entrypoint_ablation.py`, `run_ablation.sh`: the experiment
* `out/`, `out_c5/`:
  * `per_app.csv`
  * `per_library.csv`
  * `sysjava_only.csv` (syscall, entry point, Java method, call path)
  * `check.csv` (replay = recorded)
  * `logs/` (all paths)
