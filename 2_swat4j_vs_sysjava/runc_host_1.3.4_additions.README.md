# runc 1.3.4 additions to the runtime whitelist

`runc.txt` lists the syscalls the container runtime itself issues inside the
container before handing over to the application. It predates the host's
runc 1.3.4 (Docker 29.1.3), whose init also uses the four syscalls in
`runc_host_1.3.4_additions.txt`.

Measured 2026-11-04 by running jetty_9.4.51-jdk8-buster with its generated
profile switched to `SCMP_ACT_LOG` and reading the SECCOMP audit records:
`runc:[2:INIT]` issued openat2 (x10), close_range, faccessat2 and getppid.
Denying them made runc's init panic before the application started.

They are runtime syscalls, not application ones, so they go with the runtime
whitelist. The same run showed one application-side miss (`java` calling
`fchdir`); that is an analysis gap and is deliberately NOT added here.

## fchown (added 2026-11-11, runc.txt 122 -> 123)

The JDK 8 workload validation (`workload_validation/`, profiles in SCMP_ACT_LOG mode, records read
from /var/log/audit/audit.log) showed `runc:[2:INIT]` issuing `fchown` in Elasticsearch and Jetty.
runc's init (`fixStdioPermissions`) changes the owner of the container's stdio when the container runs
as a non-root user without a terminal, and ignores the error. The 11-04 measurement above used a case
that does not hit this path, so it missed it. It is a runtime syscall, so it goes in `runc.txt`, not in
the analysis. The previous whitelist is kept as `runc.txt.bak_122_pre_fchown`.
