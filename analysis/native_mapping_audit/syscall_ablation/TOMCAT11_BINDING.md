# Tomcat 11.0.18 (JDK 25): no binding vs. SysJava's binding vs. SWAT4J's binding

## The question

Does knowing which native functions Java can call (the *binding*) change Tomcat's syscall
allowlist? We compare three ways of choosing SysPart's entry points into each native library:

| Arm | Entry points into a library |
|---|---|
| **No binding** | every function the `.so` exports (`nm -D`). This is what a tool has to assume when it cannot tell what Java calls. We also report an upper bound that uses every function the library defines, exported or not. |
| **SysJava binding** | the functions SysJava mapped: JNI static, RegisterNatives (libjvm), `JVM_` entries, and Panama FFM downcalls |
| **SWAT4J binding** | the functions SWAT4J's mapping assigns: JNI static (`Java_XXX`) and `JVM_XXX` only |

Everything else is held fixed: the binaries, SysPart's call graphs, and SysPart's search.

Tomcat 11.0.18 on JDK 25 is the one container that uses all of SysJava's newer mappings that
SWAT4J lacks:

* RegisterNatives inside libjvm;
* `JVM_` entries SWAT4J's table does not list;
* FFM: Tomcat 11 calls OpenSSL through `java.lang.foreign` instead of tomcat-native.

It has no JNA bindings.

## Short answer

* **No binding vs. SysJava:** dropping the binding adds syscalls in exactly one library,
  libcrypto, through its exported socket and secure-heap API, which Tomcat never binds.
  * Analysed libraries' union: **111 vs. 107** syscalls (direct calls only: 97 vs. 90).
  * Deployed profile: **167 vs. 166**. Only `mlock2` is new. The other extras already enter
    the profile from the `java` binary, the JDK libraries SysJava analysed without bindings, or
    the Docker runtime whitelist.
* **SWAT4J vs. SysJava:** SWAT4J gives libssl and libcrypto zero entry points, so 35 + 34
  library-level syscalls go unreached. In the analysed libraries' union this loses one syscall,
  `arch_prctl`. In the deployed profile it loses **nothing** (166 = 166), because `arch_prctl`
  is also in the Docker runtime whitelist that the pipeline merges in.
* **SysJava's binding never loses a syscall that no binding finds.** In every library and in
  both modes, SysJava's set is a subset of the no-binding set.

The honest reading for Tomcat 11: binding precision changes the deployed profile by one
syscall. The effect is visible per library (libssl, libcrypto), not in the merged profile.

## Inputs

| What | Path |
|---|---|
| SysPart graphs (JNI, libjvm) | `~/Prototype/Final_results/tomcat_11.0.18-jdk25-temurin-noble/Binary_Analysis/syscalls_output_tomcat_11.0.18-jdk25-temurin-noble/<lib>/` |
| SysPart graphs (FFM) | `.../Binary_Analysis/jna_ffi_analysis/libraries/{libssl.so.3,libcrypto.so.3}/` |
| Binaries (for `nm -D`) | `.../Dataset/LIBS_tomcat_11.0.18-jdk25-temurin-noble/`. Checksums match the copies SysPart analysed (JDK libs also under `JDK25_LIBS/`). |
| SysJava / SWAT4J syscall sets | `out_mech_latest/per_library.csv` (from `run_mechanism_latest.sh`, same numbers as [MAPPING_PER_LIBRARY.md](MAPPING_PER_LIBRARY.md)) |
| Mapping audit | `../out_tomcat11/per_method.csv`, `per_app_summary.csv` |
| Profile parts not tied to mapping | `syscalls_BIN_*/binary_syscalls.txt` (100), `syscalls_unanalysed_*/unanalysed_syscalls.txt` (86), `~/Prototype/Final_results_echotrace/dockerd_containerd_syscall.txt` (117) |
| Recorded final profile | `syscalls_output_*/tomcat_11.0.18-jdk25-temurin-noble.txt` (166) |

## How to rerun

```bash
cd ~/Tutorial/rq1_native_mapping/syscall_ablation
./run_mechanism_latest.sh        # only if out_mech_latest/ is missing (about 20 min)
./run_binding_tomcat11.sh        # about 5 min; writes out_binding_tomcat11/
```

Outputs in `out_binding_tomcat11/`:

* `per_library.csv`: per library and mode, exported and total function counts, entry points,
  syscall counts per arm, the set differences, and the full sets.
* `container.csv`: the union over the analysed libraries, per mode.
* `profile.csv`: the whole deployed profile per arm. It is the library union (full mode) plus
  the three lists above. `equals_recorded_profile` is True for SysJava's arm, which checks the
  method.

Call paths: `trace_path.py <lib_dir> <start> <syscall> --direct`.

## Native-method mapping (the 269 Java `native` methods)

| | SysJava | SWAT4J |
|---|---|---|
| JNI static (`Java_…`) | 175 | 175 |
| RegisterNatives in libjvm (`Unsafe_*`, `MHN_*`, `CONT_*`, `Perf_*`) | 43 | 0 |
| `JVM_` entries | 40 | 24 (5 more called intrinsic, 11 unmapped) |
| Intrinsic | 1 | 6 |
| Not mapped | 10 | 64 |
| **Mapped** | **258** | **199** |

(Per-library entry-point counts below are per C function, so they differ slightly: e.g. 48
libjvm functions are classified RegisterNatives.)

Separately, SysJava resolves 301 FFM downcall bindings into libssl and libcrypto (7 unresolved).
These are not Java `native` methods, so SWAT4J cannot see them at all.

SysJava does not map 10 methods. For 9 it found no matching symbol in the extracted libraries;
the 10th is a RegisterNatives entry it could not resolve:

* `Unsafe.{get,put}Reference*` and `compareAndSetReference`;
* `Object.wait0`, `VM.getNanoTimeAdjustment`, `Class.getSuperclass`;
* commons-daemon `DaemonLoader.shutdown/failed`.

## Result 1: per library

Syscalls reached. Full = SysPart's model (indirect calls go to every address-taken function).
Direct = indirect edges dropped.

| Library | Exported functions | SysJava entry points (mechanism) | SWAT4J entry points | No binding (exports) full / direct | No binding (all functions) full / direct | SysJava full / direct | SWAT4J full / direct |
|---|---|---|---|---|---|---|---|
| libjava.so | 246 | 69 (JNI) | 69 | 106 / 88 | 106 / 88 | 106 / 88 | 106 / 88 |
| libjvm.so | 212 | 88 (48 RegisterNatives, 40 `JVM_`) | 24 | 103 / 84 | 103 / 94 | 103 / 84 | 103 / 84 |
| libnet.so | 48 | 5 (JNI) | 5 | 103 / 60 | 103 / 60 | 103 / 60 | 103 / 60 |
| libzip.so | 39 | 9 (JNI) | 9 | 103 / 20 | 103 / 20 | 103 / 20 | 103 / 20 |
| **libssl.so.3** | 518 | 182 (FFM) | **0** | 35 / 35 | 35 / 35 | 35 / 35 | **0 / 0** |
| **libcrypto.so.3** | 5,363 | 101 (FFM) | **0** | **50 / 50** | 57 / 57 | 34 / 34 | **0 / 0** |
| libtcnative-2.so.0.0.12 | 141 | 0 | 0 | not measured | not measured | 0 | 0 |
| **Union** | | 454 | 107 | **111 / 97** | 114 / 110 | **107 / 90** | **106 / 89** |

Observations:

* **The JDK libraries are the same in every arm.** libjvm's RegisterNatives targets are not even
  exported, and SWAT4J roots only 24 of SysJava's 88 libjvm functions. Yet all arms reach the
  same 103 (full) and 84 (direct) syscalls. Any entry into libjvm reaches its core (allocation,
  threads, file I/O), so better libjvm mapping does not change libjvm's syscalls here.
  * The "all functions" upper bound adds 10 in direct mode: internal libjvm code that no entry
    point reaches by direct calls.
* **libssl:** 182 bound functions out of 518 exports, but both reach the same 35 syscalls.
  SWAT4J reaches none.
* **libcrypto is where binding pays off against no binding.** Tomcat binds 101 of libcrypto's
  5,363 exports. The other exports add 16 syscalls:
  `accept bind connect getsockname getsockopt ioctl listen mlock2 poll pselect6 readv recvmsg
  sendto setsockopt socket uname`.
  They come from OpenSSL's socket BIO and secure-heap API, which Tomcat does not use
  (Tomcat does its own networking through NIO):

  ```
  BIO_listen       -[DIRECT]-> listen      -[syscall]-> listen      (also getsockopt)
  BIO_accept_ex    -[DIRECT]-> accept      -[syscall]-> accept
  BIO_socket_wait  -[DIRECT]-> select      -[syscall]-> pselect6
  BIO_lookup_ex / BIO_socket / BIO_connect                  -> socket, connect
  CRYPTO_secure_malloc_init                -[syscall]-> mlock2
  ```

* **libtcnative is shipped but never bound.** Tomcat 11 uses FFM for OpenSSL instead of the APR
  connector. SysJava finds no binding, so SysPart never built its graph (empty `callgraph.json`).
  A tool without binding would have to analyse all 141 exports as well. We cannot measure that
  without running SysPart on it, so the no-binding numbers are a **lower bound** on its cost.

## Result 2: the deployed profile

The deployed profile is the analysed libraries' union (full mode) plus three parts that don't
depend on mapping:

* the `java` binary;
* the JDK libraries loaded without Java bindings (libnio, libmanagement, …, from SysJava's
  "unanalysed" step);
* the Docker/containerd runtime whitelist.

| Arm | Profile size | vs. SysJava |
|---|---|---|
| No binding (exports) | 167 | + `mlock2` |
| No binding (all functions) | 167 | + `mlock2` |
| **SysJava binding** | **166** | = recorded profile ✔ |
| SWAT4J binding | 166 | same; `arch_prctl` (lost from libssl) is in the runtime whitelist |

So libcrypto's 16 extra syscalls from no binding mostly disappear in the merged profile. Only
`mlock2` is new. The others already enter the profile through other parts.

## Result 3: SWAT4J's miss, with path

```
SSL_do_handshake -[DIRECT]-> (static helper 0x33af0) -[DIRECT]-> ASYNC_start_job
  -[DIRECT]-> swapcontext -[syscall]-> arch_prctl
```

Runtime evidence that the FFM path is live: the sysdig capture shows the `java` process opening
`libssl.so.3` and `libcrypto.so.3` (`Dynamic_Analysis/sysdig_outputs_*/libs_by_pid.txt`).
The capture records loaded libraries only, not syscalls, so it cannot confirm individual
syscalls.

## Limitations

* **No binding = exported functions of the libraries SysJava analysed.** A binding-free tool
  would also have to analyse libtcnative (above) and every other `.so` in the image. That is
  not measured here.
* **Docker whitelist dominates the merged profile.** At 117 syscalls it hides most per-library
  differences. Per-library and union numbers show the effect of mapping. The profile shows what
  a user deploys.
* **Static reachability only.** `mlock2` (secure heap) and `arch_prctl` (OpenSSL async jobs) are
  real code paths, but whether Tomcat ever takes them depends on configuration.

## What this changes in MAPPING_PER_LIBRARY.md

That document counts misses in the **union of the analysed libraries**, which is what
`mechanism_ablation.py` computes. Measured against the **deployed profile** (with the binary,
unanalysed libraries and Docker whitelist added):

* Tomcat 11 loses nothing.
* By the same check, Elasticsearch 7.1.0 loses only `mlockall`; the other six are in its binary,
  unanalysed-library or whitelist lists.
* Cassandra 3.0.29 loses `mlockall` and `munlockall`.

The ES and Cassandra figures are a quick grep over those lists, not yet a scripted
`profile.csv`; see observation O12 in [REPRODUCE.md](../REPRODUCE.md).
