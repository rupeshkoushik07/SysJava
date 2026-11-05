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
