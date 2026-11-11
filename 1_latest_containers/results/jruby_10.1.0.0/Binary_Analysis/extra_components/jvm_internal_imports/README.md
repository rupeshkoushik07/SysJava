# libjvm internals, via the functions libjvm imports

The java launcher binds libjvm through dlsym, so libjvm's start-up code and internal threads are not
reachable from its mapped JNI start functions. SysPart ran on each library libjvm imports from
(DT_NEEDED), starting from only the functions libjvm imports from it (start_<lib>.txt).
Made by scripts/analyse_jvm_imports.sh jruby_10.1.0.0. Per-library runs: runs.txt. Union: syscalls.txt.
With JVMI_DLSYM_LIBS: also the C-library functions that analysed libraries look up by name with dlsym
(dlsym_names.tsv: library, provider, names), added to the same start lists.
