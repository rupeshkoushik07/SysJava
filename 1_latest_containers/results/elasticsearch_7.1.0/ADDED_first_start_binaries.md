
# Executables: _start + main start functions (2026-11-05 23:09)

elasticsearch_7.1.0: basename bash chroot dirname env grep id java ldconfig runc uname were rerun with starts `_start` + `main` (plus `uu_<tool>::uumain` for uutils
multi-call binaries), the rule automate_syscall_analysis.sh now applies to every dynamically linked
executable. In non-PIE binaries _start hands main to __libc_start_main as an absolute immediate that
SysPart does not follow, so analysed from `_start` alone they only got libc's startup syscalls.
Previous results are kept in Binary_Analysis_before_main/.
