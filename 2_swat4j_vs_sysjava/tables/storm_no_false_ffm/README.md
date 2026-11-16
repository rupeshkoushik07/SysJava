# Storm profile without `sync`, after the 2026-11-11 analysis fixes

Same as `../storm_no_false_ffm_rta/` (172): Storm's pipeline profile minus `sync`, which comes only from false
FFM hits (Clojure class names, see ../REPRODUCE.md). Made from the pipeline profile after the fixes
(vtable starts, libjvm imports, fchown in runc.txt; 180), so 179 syscalls.

The profile in `../../sysjava_results/storm_2.4.0-jdk8-buster/` (top level and
`Binary_Analysis/syscalls_output_storm_2.4.0-jdk8-buster/`, JSON and plain list) is replaced by this 179-syscall
file (2026-11-16), so the results, the paper and the workload validation all use the same Storm profile.
