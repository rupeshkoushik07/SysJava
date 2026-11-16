# Effect of RTA (RTA-effect table)

Same JARs and pipeline, with and without RTA in the bytecode walk; both runs predate the
2026-11-11 analysis fixes (no vtable starts, no libjvm imports).

* `rta_vs_nonrta.json`, per image: `javalib_before` / `javalib_after` = Java-library syscalls
  without / with RTA (the table's *Syscalls* columns), `javalib_added` = the syscalls RTA adds,
  `natives_new` = native methods found only with RTA.
* Cassandra: the run without RTA stopped after the bytecode stage, so SysPart was run later on its
  unchanged start lists: `cassandra_3.0.29_nonrta_library_syscalls.txt` (120). With RTA: 124
  (`chmod`, `rename`, `utimes`, `fdatasync` added).
* The table's *Natives w/o RTA* column is SWAT4J's native-method count (its walk follows only the
  named type), from `2_swat4j_vs_sysjava/tables/tab_results.md`; *Natives RTA* is SysJava's.
