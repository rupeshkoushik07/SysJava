
# Multi-call binary: per-tool uumain start (2026-11-05 21:05)

orientdb_3.2.53's coreutils (dirname env uname) are links to ONE uutils multi-call binary that dispatches on argv[0]
through a table SysPart does not follow; analysed from `_start` alone they only got the shared startup
syscalls. Each was rerun with starts `_start` + its own `uu_<tool>::uumain` (same SysPart build and
wrapper); the `_start`-only results are kept in Binary_Analysis_before_uumain/.

# Multi-call binary: per-tool uumain start (2026-11-05 21:18)

orientdb_3.2.53's coreutils (dirname env uname) are links to ONE uutils multi-call binary that dispatches on argv[0]
through a table SysPart does not follow; analysed from `_start` alone they only got the shared startup
syscalls. Each was rerun with starts `_start` + its own `uu_<tool>::uumain` (same SysPart build and
wrapper); the `_start`-only results are kept in Binary_Analysis_before_uumain/.

# Multi-call binary: per-tool uumain start (2026-11-05 21:20)

orientdb_3.2.53's coreutils (dirname env uname) are links to ONE uutils multi-call binary that dispatches on argv[0]
through a table SysPart does not follow; analysed from `_start` alone they only got the shared startup
syscalls. Each was rerun with starts `_start` + its own `uu_<tool>::uumain` (same SysPart build and
wrapper); the `_start`-only results are kept in Binary_Analysis_before_uumain/.
