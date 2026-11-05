
# Multi-call binary: per-tool uumain start (2026-11-05 21:07)

jetty_12.1.10's coreutils (date expr whoami) are links to ONE uutils multi-call binary that dispatches on argv[0]
through a table SysPart does not follow; analysed from `_start` alone they only got the shared startup
syscalls. Each was rerun with starts `_start` + its own `uu_<tool>::uumain` (same SysPart build and
wrapper); the `_start`-only results are kept in Binary_Analysis_before_uumain/.
