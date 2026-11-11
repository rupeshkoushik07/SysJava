# libjvm internals, via the functions libjvm imports

The java launcher binds libjvm through dlsym, so libjvm's start-up code and internal threads are not
reachable from its mapped JNI start functions. SysPart ran on each library libjvm imports from
(DT_NEEDED), starting from only the functions libjvm imports from it (start_<lib>.txt).
Made by scripts/analyse_jvm_imports.sh tomcat_7.0-jdk8-buster. Per-library runs: runs.txt. Union: syscalls.txt.
