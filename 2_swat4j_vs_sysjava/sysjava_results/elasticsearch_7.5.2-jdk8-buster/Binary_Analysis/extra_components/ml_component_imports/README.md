# Elastic ML component: syscalls recovered through its imports (2026-11-06)

elasticsearch_7.5.2-jdk8-buster failed under its profile (178 syscalls): Elastic's ML `controller` could
not start, so Elasticsearch aborted ("Failure running machine learning native code"). SysPart crashes on
`controller` (all 135 starts) and on almost every start of libMlCore / libboost_log(_setup).

Method (static, no SysPart run on the crashing binaries):
1. ML set = controller + libMlCore.so + the 10 Boost libraries it loads (`ml_set.txt`).
2. None of the 12 contains a direct SYSCALL instruction (objdump), so every syscall goes through a
   function imported from outside the set.
3. External imports (nm -D --undefined-only minus symbols defined inside the set), grouped by the library
   that defines them (`start_<lib>.txt`): libstdc++ 385, libc 158, libpthread 47, libxml2 30, libz 12,
   libm 2, librt/libgcc_s/libdl/ld-linux 1. Unresolved: 3 weak placeholders (_ITM_*, __gmon_start__).
4. SysPart (same build/compute_syscalls.sh as the JDK 8 pipeline) on each of those libraries from only
   the imported functions (`run.sh`, `syspart_<lib>/`). Union: 89 syscalls (`ml_component_syscalls.txt`).
Result: 3 not in the profile: mknod, sched_setparam, setsid (`new_vs_profile.txt`).
Check: the profile + those 3 (`es_profile_plus_ml_imports.json`) -> Elasticsearch starts and answers
HTTP 9200, no ML error (same docker run arguments as the pipeline's stage-10 test).
Not merged into the pipeline profile (user decision pending).
