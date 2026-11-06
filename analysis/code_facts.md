# How binding recovery works, with pointers to the code

Each row is a statement about binding recovery and where the shipped code does
it. Java sources are in `echotrace/src/main/java/com/echotrace/app/bytecode_new/`;
pipeline scripts are in `1_latest_containers/scripts/` (the same in
`2_swat4j_vs_sysjava/scripts/`). Line numbers are those of the shipped files.

| Statement | Code |
|---|---|
| Application JARs are swept for native methods. The container's JDK is on the class path but not swept; a JDK native method is included when application code reaches it (a call, a class initialiser `<clinit>` on first use, or an inherited method) | `PrototypeFinal.java`: `traceJarFiles` (line 720) sweeps `JARFILES_<image>`, `RUNTIME_<image>` is on the class loader; `visitClassInit` (1086) and `resolveAndVisit` (1106), detector commit `52628c4` |
| The JNA, JNR-FFI and FFM detectors scan only application classes | the detectors run on `JARFILES_<image>` only |
| A binding whose library or symbol is unknown (`<?>`) gives no start function | `analyse_jna_ffi.py`, lines 110-120 (`UNRESOLVED_LIBS`, line 38) |
| JNI: the library is chosen by symbol (`nm -D --defined-only` over `LIBS_<image>`); `RegisterNatives` bindings come from the decoded registration tables | `mapped_updated.py` (line 914) |
| JNA, JNR-FFI, FFM: the library name selects the file; a start function gets an address only if it is in SysPart's `allfunctions.txt` (the library and its loaded dependencies) | `analyse_jna_ffi.py`; `compute_syscalls_lowmem.sh`, lines 150-155 |
| Library names are normalised: lower case, leading `lib` removed, cut at the first `.so`/`.dylib`/`.dll`; SONAMEs are indexed; the default library is `c` | `NativeLibraryNames.java`; `normalize_key` in `analyse_jna_ffi.py` (line 55) |
| JNA direct mapping: every native method of a registered class. JNR-FFI: all interface methods when no call is visible | `JnaDirectMapDetector.java` (line 211); `JnrFfiDetector.java`, PASS 3 (line 243) |
| Unresolved bindings are classified by a keyword rule: `linux`, `unixsocket`, `RubyBasicSocket$LibC` -> libc (ZooKeeper 7, Groovy 7, JRuby 16); FreeBSD, macOS, Solaris and Windows variants and FFM upcalls -> other platform | `1_latest_containers/unavailable_libs/notfound_search/binding_overrides.py` (line 21) |
| The only manual step: libraries the images do not ship were supplied (Solr netty-tcnative, Storm jansi and io_uring, Tomcat jsvc, OrientDB jffi and NativePosixUtil, Elasticsearch NativePosixUtil) and then mapped by the pipeline | `1_latest_containers/unavailable_libs/PROVENANCE.tsv` |

Known limitations:

* calls through subclass overrides and lambdas are not followed;
* alternative library names such as `libc.so.6|msvcrt` are split wrongly;
* the FFM detector also infers hits from class names (`FfiDetector.java`, lines
  217-241, run on every class). Table III drops an FFM hit when its JAR has no
  class that references `java/lang/foreign` (`tools/make_paper_table_latest.py`).
  The generated profiles still include the syscalls of those hits (Storm's
  profile allows `sync`, which came only from `clojure.core$sync`).
