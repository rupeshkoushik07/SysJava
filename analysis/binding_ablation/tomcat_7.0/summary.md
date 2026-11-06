# SysJava with and without binding recovery: tomcat_7.0

- **Container:** `et_tomcat_7.0`, image `tomcat:7.0` (`sha256:9dfd74e6bc2f`)
- **Application:** Apache Tomcat 7.0.109
- **Distro:** Debian GNU/Linux 10.10 (buster)
- **JDK:** JDK 8 (OpenJDK, `/usr/local/openjdk-8`)
- **Native libraries:** tomcat-native 1.2.28, OpenSSL 1.1.1d-0+deb10u6, APR 1.6.5-1+b1, glibc 2.28-10

| Library | Binding: start functions | Binding: syscalls | No binding: start functions | No binding: syscalls |
|---|---:|---:|---:|---:|
| libj2pkcs11.so | 67 | 37 | 163 | 37 |
| libjava.so | 88 | 86 | 363 | 96 |
| libjvm.so | 132 | 82 | 33,030 | 98 |
| libmanagement.so | 2 | 81 | 115 | 82 |
| libnet.so | 2 | 81 | 177 | 90 |
| libsunec.so | 5 | 37 | 387 | 37 |
| libtcnative-1.so.0.2.28 | 264 | 101 | 458 | 102 |
| libzip.so | 23 | 81 | 196 | 81 |
| **All 8 libraries** | **583** | **116** | **34,889** | **124** |

**Native methods (JNI).** SysJava's bytecode analysis found 612 native methods (Java methods declared `native`, in the application and the JDK) and mapped 583 of them to C functions: 264 in libtcnative-1.so.0.2.28, 132 in libjvm.so, 88 in libjava.so, 67 in libj2pkcs11.so, 23 in libzip.so, 5 in libsunec.so, 2 in libmanagement.so and 2 in libnet.so (451 through JNI symbol naming, 93 through RegisterNatives tables, 39 through JVM native-method tables). Of the other 29, 20 are Windows-only, 4 have no matching function in any library, 4 are handled inside the JVM (intrinsics) and 1 could not be resolved. Apache Tomcat 7.0.109 is an older application on JDK 8 and binds native code only through classic JNI.

**How the syscalls were counted.** At runtime the JVM loaded 22 native libraries (sysdig trace). The mapped functions fall in 8 libraries: 7 of those, plus libj2pkcs11.so, which is not loaded at all. For each library, SysPart builds a call graph and collects every syscall reachable from the start functions: with binding, the functions the native methods map to; without binding, every function in the library, since without the mapping any of them could be called. Both use the same library files and SysPart build. The last row adds up the start functions and counts each syscall once.

**Result.** Across the 8 libraries, starting from the mapped functions reaches 116 syscalls; starting from every function reaches 124. Per library, the gap is largest in libjvm.so (+16), libjava.so (+10) and libnet.so (+9). Reached only without binding (8): `clock_getres`, `fchdir`, `fsync`, `getppid`, `rt_sigsuspend`, `socketpair`, `times` and `umask`.

## Syscalls per library

### libj2pkcs11.so
- Binding (37): `brk`, `clock_gettime`, `close`, `exit`, `exit_group`, `fcntl`, `futex`, `getcwd`, `getdents64`, `getpid`, `getrandom`, `gettid`, `ioctl`, `lseek`, `madvise`, `mmap`, `mprotect`, `mremap`, `munmap`, `newfstatat`, `openat`, `pread64`, `prlimit64`, `read`, `rt_sigaction`, `rt_sigprocmask`, `rt_sigreturn`, `sched_get_priority_max`, `sched_get_priority_min`, `sched_getaffinity`, `sched_getparam`, `sched_getscheduler`, `sched_setscheduler`, `sysinfo`, `tgkill`, `write`, `writev`
- Only without binding (+0): none

### libjava.so
- Binding (86): `access`, `bind`, `brk`, `chdir`, `clock_gettime`, `clock_nanosleep`, `clone`, `clone3`, `close`, `connect`, `dup`, `dup2`, `execve`, `exit`, `exit_group`, `faccessat`, `faccessat2`, `fcntl`, `fstat`, `ftruncate`, `futex`, `getcwd`, `getdents64`, `getegid`, `geteuid`, `getgid`, `getgroups`, `getpid`, `getpriority`, `getrandom`, `getrusage`, `getsockname`, `gettid`, `gettimeofday`, `getuid`, `ioctl`, `kill`, `lseek`, `lstat`, `madvise`, `mincore`, `mmap`, `mprotect`, `mremap`, `munmap`, `newfstatat`, `openat`, `pipe2`, `poll`, `pread64`, `prlimit64`, `read`, `readlink`, `recvfrom`, `recvmsg`, `rseq`, `rt_sigaction`, `rt_sigprocmask`, `rt_sigreturn`, `sched_get_priority_max`, `sched_get_priority_min`, `sched_getaffinity`, `sched_getparam`, `sched_getscheduler`, `sched_setaffinity`, `sched_setscheduler`, `sched_yield`, `sendto`, `set_robust_list`, `setsockopt`, `shmat`, `shmctl`, `shmdt`, `shmget`, `socket`, `stat`, `statfs`, `sysinfo`, `tgkill`, `time`, `uname`, `unlink`, `vfork`, `wait4`, `write`, `writev`
- Only without binding (+10): `chmod`, `fsync`, `getpeername`, `mkdir`, `rename`, `rmdir`, `sendmmsg`, `setpriority`, `umask`, `utimensat`

### libjvm.so
- Binding (82): `access`, `bind`, `brk`, `clock_gettime`, `clock_nanosleep`, `clone`, `clone3`, `close`, `connect`, `dup`, `execve`, `exit`, `exit_group`, `faccessat`, `faccessat2`, `fcntl`, `fstat`, `futex`, `getcwd`, `getdents64`, `getegid`, `geteuid`, `getgid`, `getgroups`, `getpid`, `getpriority`, `getrandom`, `getrusage`, `getsockname`, `gettid`, `gettimeofday`, `getuid`, `ioctl`, `kill`, `lseek`, `lstat`, `madvise`, `mincore`, `mmap`, `mprotect`, `mremap`, `munmap`, `newfstatat`, `openat`, `poll`, `pread64`, `prlimit64`, `read`, `readlink`, `recvfrom`, `recvmsg`, `rseq`, `rt_sigaction`, `rt_sigprocmask`, `rt_sigreturn`, `sched_get_priority_max`, `sched_get_priority_min`, `sched_getaffinity`, `sched_getparam`, `sched_getscheduler`, `sched_setaffinity`, `sched_setscheduler`, `sched_yield`, `sendto`, `set_robust_list`, `setpriority`, `setsockopt`, `shmat`, `shmctl`, `shmdt`, `shmget`, `socket`, `stat`, `sysinfo`, `tgkill`, `time`, `uname`, `unlink`, `vfork`, `wait4`, `write`, `writev`
- Only without binding (+16): `accept`, `chmod`, `clock_getres`, `fchdir`, `fsync`, `ftruncate`, `getpeername`, `getsockopt`, `listen`, `mkdir`, `rename`, `rmdir`, `rt_sigsuspend`, `sendmmsg`, `shutdown`, `times`

### libmanagement.so
- Binding (81): `access`, `bind`, `brk`, `clock_gettime`, `clock_nanosleep`, `clone`, `clone3`, `close`, `connect`, `dup`, `execve`, `exit`, `exit_group`, `faccessat`, `faccessat2`, `fcntl`, `fstat`, `futex`, `getcwd`, `getdents64`, `getegid`, `geteuid`, `getgid`, `getgroups`, `getpid`, `getpriority`, `getrandom`, `getrusage`, `getsockname`, `gettid`, `gettimeofday`, `getuid`, `ioctl`, `kill`, `lseek`, `lstat`, `madvise`, `mincore`, `mmap`, `mprotect`, `mremap`, `munmap`, `newfstatat`, `openat`, `poll`, `pread64`, `prlimit64`, `read`, `readlink`, `recvfrom`, `recvmsg`, `rseq`, `rt_sigaction`, `rt_sigprocmask`, `rt_sigreturn`, `sched_get_priority_max`, `sched_get_priority_min`, `sched_getaffinity`, `sched_getparam`, `sched_getscheduler`, `sched_setaffinity`, `sched_setscheduler`, `sched_yield`, `sendto`, `set_robust_list`, `setsockopt`, `shmat`, `shmctl`, `shmdt`, `shmget`, `socket`, `stat`, `sysinfo`, `tgkill`, `time`, `uname`, `unlink`, `vfork`, `wait4`, `write`, `writev`
- Only without binding (+1): `times`

### libnet.so
- Binding (81): `access`, `bind`, `brk`, `clock_gettime`, `clock_nanosleep`, `clone`, `clone3`, `close`, `connect`, `dup`, `execve`, `exit`, `exit_group`, `faccessat`, `faccessat2`, `fcntl`, `fstat`, `futex`, `getcwd`, `getdents64`, `getegid`, `geteuid`, `getgid`, `getgroups`, `getpid`, `getpriority`, `getrandom`, `getrusage`, `getsockname`, `gettid`, `gettimeofday`, `getuid`, `ioctl`, `kill`, `lseek`, `lstat`, `madvise`, `mincore`, `mmap`, `mprotect`, `mremap`, `munmap`, `newfstatat`, `openat`, `poll`, `pread64`, `prlimit64`, `read`, `readlink`, `recvfrom`, `recvmsg`, `rseq`, `rt_sigaction`, `rt_sigprocmask`, `rt_sigreturn`, `sched_get_priority_max`, `sched_get_priority_min`, `sched_getaffinity`, `sched_getparam`, `sched_getscheduler`, `sched_setaffinity`, `sched_setscheduler`, `sched_yield`, `sendto`, `set_robust_list`, `setsockopt`, `shmat`, `shmctl`, `shmdt`, `shmget`, `socket`, `stat`, `sysinfo`, `tgkill`, `time`, `uname`, `unlink`, `vfork`, `wait4`, `write`, `writev`
- Only without binding (+9): `accept`, `dup2`, `getpeername`, `getsockopt`, `listen`, `readv`, `sendmmsg`, `shutdown`, `socketpair`

### libsunec.so
- Binding (37): `brk`, `clock_gettime`, `close`, `exit`, `exit_group`, `fcntl`, `futex`, `getcwd`, `getdents64`, `getpid`, `getrandom`, `gettid`, `ioctl`, `lseek`, `madvise`, `mmap`, `mprotect`, `mremap`, `munmap`, `newfstatat`, `openat`, `pread64`, `prlimit64`, `read`, `rt_sigaction`, `rt_sigprocmask`, `rt_sigreturn`, `sched_get_priority_max`, `sched_get_priority_min`, `sched_getaffinity`, `sched_getparam`, `sched_getscheduler`, `sched_setscheduler`, `sysinfo`, `tgkill`, `write`, `writev`
- Only without binding (+0): none

### libtcnative-1.so.0.2.28
- Binding (101): `accept`, `accept4`, `access`, `arch_prctl`, `bind`, `brk`, `chdir`, `chmod`, `clock_gettime`, `clone`, `close`, `connect`, `dup`, `dup2`, `dup3`, `epoll_create1`, `epoll_ctl`, `epoll_wait`, `execve`, `exit`, `exit_group`, `fchown`, `fcntl`, `flock`, `fstat`, `ftruncate`, `futex`, `getcwd`, `getdents64`, `geteuid`, `getgid`, `getpeername`, `getpid`, `getrandom`, `getsockname`, `getsockopt`, `gettid`, `gettimeofday`, `getuid`, `ioctl`, `kill`, `link`, `listen`, `lseek`, `lstat`, `madvise`, `mkdir`, `mmap`, `mprotect`, `mremap`, `munmap`, `newfstatat`, `openat`, `pipe2`, `poll`, `pread64`, `prlimit64`, `pselect6`, `read`, `readv`, `recvfrom`, `recvmsg`, `rename`, `rmdir`, `rt_sigaction`, `rt_sigprocmask`, `rt_sigreturn`, `sched_get_priority_max`, `sched_get_priority_min`, `sched_getaffinity`, `sched_getparam`, `sched_getscheduler`, `sched_setscheduler`, `sched_yield`, `semctl`, `semget`, `semtimedop`, `sendfile`, `sendmmsg`, `sendto`, `set_robust_list`, `setgid`, `setsid`, `setsockopt`, `setuid`, `shmat`, `shmctl`, `shmdt`, `shmget`, `shutdown`, `socket`, `stat`, `sysinfo`, `tgkill`, `time`, `uname`, `unlink`, `utimensat`, `wait4`, `write`, `writev`
- Only without binding (+1): `getppid`

### libzip.so
- Binding (81): `access`, `bind`, `brk`, `clock_gettime`, `clock_nanosleep`, `clone`, `clone3`, `close`, `connect`, `dup`, `execve`, `exit`, `exit_group`, `faccessat`, `faccessat2`, `fcntl`, `fstat`, `futex`, `getcwd`, `getdents64`, `getegid`, `geteuid`, `getgid`, `getgroups`, `getpid`, `getpriority`, `getrandom`, `getrusage`, `getsockname`, `gettid`, `gettimeofday`, `getuid`, `ioctl`, `kill`, `lseek`, `lstat`, `madvise`, `mincore`, `mmap`, `mprotect`, `mremap`, `munmap`, `newfstatat`, `openat`, `poll`, `pread64`, `prlimit64`, `read`, `readlink`, `recvfrom`, `recvmsg`, `rseq`, `rt_sigaction`, `rt_sigprocmask`, `rt_sigreturn`, `sched_get_priority_max`, `sched_get_priority_min`, `sched_getaffinity`, `sched_getparam`, `sched_getscheduler`, `sched_setaffinity`, `sched_setscheduler`, `sched_yield`, `sendto`, `set_robust_list`, `setsockopt`, `shmat`, `shmctl`, `shmdt`, `shmget`, `socket`, `stat`, `sysinfo`, `tgkill`, `time`, `uname`, `unlink`, `vfork`, `wait4`, `write`, `writev`
- Only without binding (+0): none

