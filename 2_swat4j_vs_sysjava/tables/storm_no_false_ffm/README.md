# Storm profile without `sync`, after the 2026-11-11 analysis fixes

Same as `../storm_no_false_ffm_rta/` (172): Storm's pipeline profile minus `sync`, which comes only from false
FFM hits (Clojure class names, see ../REPRODUCE.md). Made from the pipeline profile after the fixes
(vtable starts, libjvm imports, fchown in runc.txt; 180), so 179 syscalls.
