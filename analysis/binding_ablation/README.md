# Binding-recovery ablation (RQ5)

SysPart run twice per library, on the same files with the same build: from the
functions that recovered bindings map to (binding), and from every function in
the library (no binding).

| Image | Binding: starts / syscalls | No binding: starts / syscalls |
|---|---|---|
| Tomcat 7.0.109 (JDK 8), all 8 libraries | 583 / 116 | 34,889 / 124 |
| Tomcat 11.0.22 (JDK 25), all but `libjvm.so` | 357 / 116 | 12,914 / 127 |

* Procedure: `REPRODUCE.md`. Per image: `<image>/summary.md`,
  `per_library_syscalls.tsv`, `summary.tex`.
* Tomcat 7: libraries with stripped dependencies were rerun from their
  symbolized copies; an earlier summary showing 119 / 125 is superseded.
* Tomcat 11: `libjvm.so` without binding did not finish (`std::bad_alloc` at
  35 GB and 60 GB); it is shown as "n/r" and left out of the totals.
* Paths in these files are those of the analysis host. The SysPart call graphs
  of the runs (7 GB) are not included.
