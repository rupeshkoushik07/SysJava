# REPRODUCE: validation of SysJava mappings: stratified sample + JNI symbol lookup checked in full (R6, 2026-11-16; restructured 2026-11-17)

Request (user via the Rewrite session): draw a stratified random sample of SysJava's resolved mappings, 20 per
stratum, with the evidence a person can check and a pre-check verdict to confirm. Read-only: no result, table or
paper file is changed.

Restructured 2026-11-17 (user): six mechanisms are sampled, 20 each (120); JNI symbol lookup is checked in full
(all 21,058) instead of sampled. The 120 are the first 120 of the original draw (stratum 7 was drawn last), so they
and their verdicts are unchanged. The original 140 (7 x 20) outputs are kept in `sample_140_2026-11-16/`.

**Who decided the verdicts.** Every verdict in `sample.tsv`, `sample.md` and `jni_symbol_lookup_all.tsv` is computed
by `sample.py` from the evidence it prints. The only verdict decided by a person is S2-10 (user, 2026-11-16). A
manual confirmation of the 120 is not recorded in these files.

## Command

    cd ~/Tutorial/EchoTrace/manual_validation
    python3 population.py   # population sizes per stratum (printed)
    python3 sample.py       # ~2 min: sample.tsv (120), sample.md, population_sizes.tsv, jni_symbol_lookup_all.tsv (21,058)
    python3 exhaustive/exhaustive.py   # optional, ~4 min: the same check on every mapping of all 7 strata -> exhaustive/all.tsv

Seed 20261116 (`SEED` in sample.py). Python 3.10, pyelftools 0.33. Same inputs, same seed, same output.

## Inputs (read only)

- Table II (JDK 8 set): `Final_results_JDK8/<img>-jdk8-buster/Bytecode_Analysis/outputs_<img>/` (10 images)
- Table III (latest set): `EchoTrace_latest/Final_results_latest_versions_rta/<img>/Bytecode_Analysis/outputs_<img>/`
  (10 images)
  - `mapped_method_syscalls.txt` (JNI mapper output; tag per mapping), `native_methods.txt` (natives counted in the
    tables; mappings of other methods are left out), `jni_dynamic_bindings.txt` and `jvm_dynamic_mapping.txt`
    (RegisterNatives tables the pipeline extracted), `jna_hits.txt` (binding detector)
- Manual mappings: `EchoTrace_latest/unavailable_libs/<img>/mapping/` (JDK 8) and `mapping_rta/` (latest), with
  `PROVENANCE.tsv` and `NOTES.md`; `binding_overrides.tsv` (Tomcat 11, JRuby 10.1.0.0; the JDK 8 JRuby uses
  the 10.1.0.0 file, as Table II's JNR-FFI count does)
- Library files: the images' `Dataset/LIBS_<img>/` (sha256 in the table); symbol addresses from the
  `Dataset_symbolized/` copy where present (same code, symbols added)

## Population and strata

One mapping = (image, Java method or binding, native function, library file); mapper lines with a `?` tag or
NOT_FOUND are unresolved and left out; repeated lines count once.

| Stratum | Rule | Population | JDK 8 | Latest |
|---|---|---:|---:|---:|
| 1 explicit registration | JNI_DYNAMIC, REGISTERED, and JVM-tagged mappings listed in jvm_dynamic_mapping.txt | 7,790 | 2,544 | 5,246 |
| 2 name heuristic / bridge | NETTY, DIRECT_LIBC_BRIDGE, SIGAR_LIST_BRIDGE, and JVM-tagged mappings from the mapper's built-in JVM_* table | 152 | 28 | 124 |
| 3 JNA | jna_hits.txt directmap / iface / dyn with library and function recovered, or override "mapped" | 110 | 41 | 69 |
| 4 JNR-FFI | jna_hits.txt jnr-ffi, same rule | 67 | 33 | 34 |
| 5 FFM | ffi hits of Tomcat 11 and ZooKeeper 3.9.5 (the only images that use java.lang.foreign), one per symbol | 206 | 0 | 206 |
| 6 manual / supplied library | resolved lines of the manual mapping files | 943 | 411 | 532 |
| 7 JNI symbol lookup (checked in full, not sampled) | JNI-tagged mappings to a Java_* symbol | 21,058 | 8,634 | 12,424 |

Counts are mappings, not methods: overloads and several library copies of one function count separately, and the
same libjvm mapping counts once per image.

Draw (sample.py `draw`, strata 1-6; `FULL = {7}` is checked in full): each stratum is shuffled, grouped by image, and taken round-robin over the images (image
order shuffled) until 20, so every image with mappings in the stratum is sampled where possible.

## Evidence and pre-check (sample.py)

- Explicit registration: the JNINativeMethod entry `{name, signature, fnPtr}` decoded from the library's
  relocations (elfev.py: R_X86_64_RELATIVE / R_X86_64_64 triples), with virtual address and file offset, and the
  chosen function's address (nm / nm -D line). Correct = an entry named like the Java method points to the chosen
  function.
- Heuristic / bridge: the rule that matched and the function's nm line; Netty mappings also checked against the
  library's JNINativeMethod table.
- JNA / JNR-FFI / FFM: the detector row (call site or interface, load call, JAR) and an nm -D line of the library
  that exports the function (the named library, a DT_NEEDED dependency that dlsym on its handle reaches, or, for
  FFM, libc through the Linker's default lookup). Bindings declared for another OS (Windows, macOS, FreeBSD,
  Solaris classes; kevent/kqueue) are "unverifiable: other-OS".
- Manual: the manual mapping line, the nm line in the supplied library, the expected JNI name, and the
  PROVENANCE.tsv / NOTES.md record (upstream version and whether it matches what the app ships or loads).
- JNI symbol lookup (all 21,058): the expected JNI short name computed from class and method (mangling of _, $, etc.),
  or its overloaded form (short name + `__<mangled args>`), and the library defines the symbol.

## Observations (script verdicts; 120 sampled + 21,058 checked in full)

- Sample, 120: correct 100 (incl. 6 with a library-name note and 2 with a version note), incorrect 0, unverifiable 20.
  The 20 are bindings shown not to resolve in these Linux images (other OS, or a function the image's library does
  not export); see below.
- JNI symbol lookup, all 21,058: 21,056 pass. 2 do not (Cassandra 5.0.8, zstd-jni 1.5.7-2):
  `Zstd.searchLengthMax` -> `Java_com_github_luben_zstd_Zstd_searchLogMax` and `Zstd.searchLengthMin` ->
  `..._searchLogMin`. The mapper records them as aliases of `searchLogMax`/`searchLogMin` (mapped_method_syscalls.txt:
  "(alias of ...)"); the library exports no `searchLength*` symbol. Not resolved whether this is correct.
- Original 140 (2026-11-16): the 20 symbol-lookup mappings sampled then were all correct; they are in
  `sample_140_2026-11-16/`.
- S2-10 (Cassandra 3.0.29 NativeLibraryLinux.fcntl -> fcntl, recorded in libjvm.so): libjvm.so only imports fcntl,
  but the pipeline's SysPart run of libjvm.so starts fcntl at 0xea7b0 in libc.so.6 (startfuncs_with_addr.txt +
  allfunctions.txt module), i.e. libc's fcntl body. Pre-check "correct" (user, 2026-11-16): library recorded as an
  importing library; function resolves to libc's fcntl in the dependency graph; syscalls unaffected. sample.py
  checks this for every libc bridge whose library does not define the function (start_module).
- The whole DIRECT_LIBC_BRIDGE population (20 mappings, Cassandra 3.0.29 / 5.0.8, Storm 2.8.8): 13 name a library
  that does not define the function (libjvm.so 10, libjffi-1.2.so 2, libjava.so 1). How each start resolves in that
  library's pipeline run:
  - libc's function: 9 (3.0.29 getpid, fcntl, strerror; 5.0.8 getpid, close, fcntl, fsync, strerror, mmap)
  - libpthread's same-named cancellation wrapper (glibc 2.28): 3 (3.0.29 close, open, fsync); same syscalls
  - not a start (absent from libjava.so's start list): 1 (5.0.8 open)
  No syscall is lost: the JNA libc run of each image starts from close, fcntl, fsync, getpid, open, strerror in
  libc itself (jna_ffi_analysis/startfuncs/libc*.txt), and mmap resolves to libc in libjffi's run.
- Unverifiable 20: 18 other-OS bindings (Windows kernel32/Kernel32, macOS sandbox_init, FreeBSD jline classes,
  BSD kevent/kqueue) that the detector resolves by name but that cannot exist in a Linux image; 2 Tomcat 11 FFM
  downcalls taken only for BoringSSL / OpenSSL 1.x (openssl_h_Macros.SSL_CTX_set1_groups_list,
  openssl_h_Compatibility.EVP_PKEY_bits), which the image's OpenSSL 3 does not export.
- Library-name note (6, FFM ZooKeeper 3.9.5): jline's ffm CLibrary is recorded with library "util", the image has no
  libutil; the functions are libc's, reached through the default lookup.
- Version note (2): Storm 2.8.8 io_uring library (mapped by user decision, Storm cannot load it); Tomcat 11
  libfallbackLinker.so built from jdk-25.0.3+9 (the image's JDK) but not shipped by the image.
