# Binding vs no binding with Binding = Java (base): all ten JDK 8 images (static analysis only)

Binding = every binding SysJava uses (JNI natives with overloads, RegisterNatives and manual mappings, vtable starts, libjvm.so, JNA, the libjvm imports step; plus JRuby's JNR-FFI libc functions and OrientDB's supplied libjffi-1.2.so), after the 2026-11-11 analysis fixes. No binding = SysPart from every function of the same library files. All images: JDK 8u504 (Eclipse Temurin), Debian 10.

| Image | Libraries | Binding: start functions | Binding: syscalls | No binding: start functions | No binding: syscalls | Profile with binding | Profile without binding | Added to profile |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Apache ZooKeeper 3.4.14 | 16 | 1,065 | 113 | 39,079 | 276 | 192 | 297 | +105 |
| Apache Tomcat 7.0.109 | 19 | 1,404 | 128 | 40,117 | 276 | 173 | 288 | +115 |
| Apache Cassandra 3.0.29 | 21 | 1,499 | 127 | 40,564 | 276 | 230 | 304 | +74 |
| Eclipse Jetty 9.4.51 | 13 | 668 | 100 | 37,406 | 276 | 161 | 296 | +135 |
| Apache Storm 2.4.0 | 19 | 3,317 | 133 | 48,135 | 277 | 179 | 290 | +111 |
| OrientDB 3.2.19 | 23 | 1,300 | 115 | 40,483 | 276 | 174 | 296 | +122 |
| Elasticsearch 7.5.2 | 19 | 1,233 | 118 | 39,637 | 276 | 185 | 296 | +111 |
| Apache Solr 8.7.0 | 23 | 1,586 | 131 | 41,237 | 276 | 201 | 291 | +90 |
| Apache Groovy 4.0.0 | 20 | 1,123 | 113 | 39,418 | 276 | 189 | 296 | +107 |
| JRuby 9.4.2.0 | 12 | 910 | 104 | 36,810 | 276 | 168 | 296 | +128 |
| **Mean** | | | | | | **185.2** | **295.0** | +109.8 |

## Checks

| Image | Java (base) | Binding syscalls | Binding − Java (base) | Java (base) − Binding | Binding − No binding | Not resolved |
|---|---:|---:|---|---|---|---|
| Apache ZooKeeper 3.4.14 | 113 | 113 | — | — | — | — |
| Apache Tomcat 7.0.109 | 128 | 128 | — | — | — | — |
| Apache Cassandra 3.0.29 | 127 | 127 | — | — | — | — |
| Eclipse Jetty 9.4.51 | 100 | 100 | — | — | — | — |
| Apache Storm 2.4.0 | 133 | 133 | — | — | — | — |
| OrientDB 3.2.19 | 115 | 115 | — | — | — | — |
| Elasticsearch 7.5.2 | 118 | 118 | — | — | — | — |
| Apache Solr 8.7.0 | 131 | 131 | — | — | — | — |
| Apache Groovy 4.0.0 | 113 | 113 | — | — | — | — |
| JRuby 9.4.2.0 | 103 | 104 | getpeername | — | — | — |

## Apache ZooKeeper 3.4.14 (`zookeeper_3.4.14-jdk8-buster`)

| Library | Bound by | Binding: start functions | Binding: syscalls | No binding: start functions | No binding: syscalls | Only without binding |
|---|---|---:|---:|---:|---:|---|
| libawt.so | JNI | 63 | 75 | 850 | 78 | +3 (getitimer, set_tid_address, setitimer) |
| libawt_headless.so | JNI | 1 | 0 | 93 | 76 | +76 |
| libawt_xawt.so | JNI | 18 | 95 | 778 | 97 | +2 (pipe, set_tid_address) |
| libfontmanager.so | JNI | 284 | 75 | 799 | 76 | +1 (set_tid_address) |
| libj2gss.so | JNI | 1 | 35 | 61 | 35 | +0 |
| libjava.so | JNI | 117 | 84 | 361 | 92 | +8 (chmod, fsync, getegid, getgid, getuid, set_tid_address, umask, utimes) |
| libjvm.so | JNI/JVM | 198 | 76 | 30,838 | 92 | +16 |
| libmanagement.so | JNI | 13 | 75 | 119 | 77 | +2 (set_tid_address, times) |
| libnet.so | JNI | 37 | 80 | 181 | 82 | +2 (readv, set_tid_address) |
| libnio.so | JNI | 22 | 81 | 193 | 111 | +30 |
| libzip.so | JNI | 34 | 75 | 213 | 76 | +1 (set_tid_address) |
| libm-2.28.so | imports | 6 | 35 | 907 | 35 | +0 |
| libdl-2.28.so | imports | 6 | 35 | 29 | 35 | +0 |
| libpthread-2.28.so | imports | 60 | 62 | 312 | 79 | +17 |
| libc-2.28.so | imports | 201 | 83 | 3,128 | 273 | +190 |
| ld-linux-x86-64.so.2 | imports | 4 | 25 | 217 | 28 | +3 (access, arch_prctl, brk) |
| **All libraries** | | **1,065** | **113** | **39,079** | **276** | +163 |

Profile: 192 syscalls with binding; 297 without binding (+105: _sysctl, accept4, acct, adjtimex, clock_adjtime, clock_nanosleep, clock_settime, copy_file_range, creat, create_module, delete_module, dup3, execveat, fallocate, fanotify_init, fanotify_mark, fchmodat, futimesat, get_kernel_syms, getcpu, getitimer, getpmsg, init_module, inotify_add_watch, inotify_init, inotify_init1, inotify_rm_watch, ioperm, iopl, lchown, link, linkat, memfd_create, mkdirat, mknod, mknodat, mlock2, mlockall, modify_ldt, msgctl, msgget, msgrcv, msgsnd, munlockall, name_to_handle_at, nfsservctl, open_by_handle_at, pivot_root, pkey_alloc, pkey_free, pkey_mprotect, ppoll, preadv, preadv2, process_vm_readv, process_vm_writev, ptrace, putpmsg, pwritev, pwritev2, query_module, quotactl, readahead, reboot, recvmmsg, remap_file_pages, renameat, renameat2, rt_tgsigqueueinfo, sched_rr_get_interval, sched_setparam, semctl, semget, semop, semtimedop, setdomainname, setfsgid, setfsuid, sethostname, setns, setsid, settimeofday, signalfd4, swapoff, swapon, symlink, symlinkat, sync, sync_file_range, syncfs, syslog, tee, timerfd_create, timerfd_gettime, timerfd_settime, truncate, unshare, uselib, ustat, utime, utimensat, utimes, vhangup, vmsplice, waitid).

## Apache Tomcat 7.0.109 (`tomcat_7.0-jdk8-buster`)

| Library | Bound by | Binding: start functions | Binding: syscalls | No binding: start functions | No binding: syscalls | Only without binding |
|---|---|---:|---:|---:|---:|---|
| libawt.so | JNI | 20 | 75 | 850 | 78 | +3 (getitimer, set_tid_address, setitimer) |
| libawt_headless.so | JNI | 1 | 0 | 93 | 76 | +76 |
| libawt_xawt.so | JNI | 11 | 95 | 778 | 97 | +2 (pipe, set_tid_address) |
| libfontmanager.so | JNI | 263 | 75 | 799 | 76 | +1 (set_tid_address) |
| libj2gss.so | JNI | 1 | 35 | 61 | 35 | +0 |
| libj2pkcs11.so | JNI | 67 | 35 | 166 | 35 | +0 |
| libjava.so | JNI | 136 | 85 | 361 | 92 | +7 (chmod, fsync, getegid, getgid, getuid, set_tid_address, umask) |
| libjvm.so | JNI/JVM | 202 | 76 | 30,838 | 92 | +16 |
| libmanagement.so | JNI | 33 | 75 | 119 | 77 | +2 (set_tid_address, times) |
| libnet.so | JNI | 34 | 80 | 181 | 82 | +2 (readv, set_tid_address) |
| libnio.so | JNI | 26 | 82 | 193 | 111 | +29 |
| libsunec.so | JNI | 38 | 35 | 414 | 35 | +0 |
| libtcnative-1.so.0 = libtcnative-1.so.0.2.28 | JNI | 264 | 99 | 458 | 101 | +2 (getppid, set_tid_address) |
| libzip.so | JNI | 31 | 75 | 213 | 76 | +1 (set_tid_address) |
| libm-2.28.so | imports | 6 | 35 | 907 | 35 | +0 |
| libdl-2.28.so | imports | 6 | 35 | 29 | 35 | +0 |
| libpthread-2.28.so | imports | 60 | 62 | 312 | 79 | +17 |
| libc-2.28.so | imports | 201 | 83 | 3,128 | 273 | +190 |
| ld-linux-x86-64.so.2 | imports | 4 | 25 | 217 | 28 | +3 (access, arch_prctl, brk) |
| **All libraries** | | **1,404** | **128** | **40,117** | **276** | +148 |

Profile: 173 syscalls with binding; 288 without binding (+115: _sysctl, acct, adjtimex, clock_adjtime, clock_nanosleep, clock_settime, copy_file_range, creat, create_module, delete_module, execveat, fallocate, fanotify_init, fanotify_mark, fchmodat, fchownat, fgetxattr, flistxattr, fremovexattr, fsetxattr, futimesat, get_kernel_syms, getcpu, getitimer, getpmsg, getxattr, init_module, inotify_add_watch, inotify_init, inotify_init1, inotify_rm_watch, ioperm, iopl, lchown, lgetxattr, linkat, listxattr, llistxattr, lremovexattr, lsetxattr, memfd_create, mkdirat, mknod, mknodat, mlock2, mlockall, modify_ldt, mount, msgctl, msgget, msgrcv, msgsnd, munlockall, name_to_handle_at, nfsservctl, open_by_handle_at, pivot_root, pkey_alloc, pkey_free, pkey_mprotect, ppoll, preadv, preadv2, process_vm_readv, process_vm_writev, ptrace, putpmsg, pwritev, pwritev2, query_module, quotactl, readahead, reboot, recvmmsg, remap_file_pages, removexattr, renameat, renameat2, rt_sigqueueinfo, rt_sigtimedwait, rt_tgsigqueueinfo, sched_rr_get_interval, sched_setparam, semtimedop, setdomainname, setfsgid, setfsuid, sethostname, setns, settimeofday, setxattr, signalfd4, splice, swapoff, swapon, symlink, symlinkat, sync, sync_file_range, syncfs, syslog, tee, timerfd_create, timerfd_gettime, timerfd_settime, truncate, umount2, unshare, uselib, ustat, utime, utimensat, vhangup, vmsplice, waitid).

## Apache Cassandra 3.0.29 (`cassandra_3.0.29-jdk8-buster`)

| Library | Bound by | Binding: start functions | Binding: syscalls | No binding: start functions | No binding: syscalls | Only without binding |
|---|---|---:|---:|---:|---:|---|
| libawt.so | JNI | 62 | 75 | 850 | 78 | +3 (getitimer, set_tid_address, setitimer) |
| libawt_headless.so | JNI | 1 | 0 | 93 | 76 | +76 |
| libawt_xawt.so | JNI | 18 | 95 | 778 | 97 | +2 (pipe, set_tid_address) |
| libc-2.28.so | JNI, JNA, imports | 204 | 86 | 3,125 | 273 | +187 |
| libfontmanager.so | JNI | 284 | 75 | 799 | 76 | +1 (set_tid_address) |
| libjava.so | JNI | 141 | 86 | 361 | 92 | +6 (ftruncate, getegid, getgid, getuid, set_tid_address, umask) |
| libjnidispatch.so | JNI | 69 | 35 | 124 | 35 | +0 |
| libjvm.so | JNI/JVM | 210 | 77 | 30,838 | 92 | +15 |
| liblz4-java.so = liblz4-java1864768816310256501.so = liblz4-java3154006651160629592.so | JNI | 19 | 35 | 93 | 35 | +0 |
| libmanagement.so | JNI | 26 | 75 | 119 | 77 | +2 (set_tid_address, times) |
| libnet.so | JNI | 41 | 80 | 181 | 82 | +2 (readv, set_tid_address) |
| libnetty-transport-native-epoll.so | JNI | 107 | 68 | 137 | 69 | +1 (set_tid_address) |
| libnio.so | JNI | 40 | 82 | 193 | 111 | +29 |
| libsctp.so | JNI | 22 | 81 | 47 | 82 | +1 (set_tid_address) |
| libsigar-amd64-linux.so | JNI | 127 | 60 | 427 | 60 | +0 |
| libsnappyjava.so | JNI | 15 | 35 | 721 | 35 | +0 |
| libzip.so | JNI | 37 | 75 | 213 | 76 | +1 (set_tid_address) |
| libm-2.28.so | imports | 6 | 35 | 907 | 35 | +0 |
| libdl-2.28.so | imports | 6 | 35 | 29 | 35 | +0 |
| libpthread-2.28.so | imports | 60 | 62 | 312 | 79 | +17 |
| ld-2.28.so | imports | 4 | 25 | 217 | 28 | +3 (access, arch_prctl, brk) |
| **All libraries** | | **1,499** | **127** | **40,564** | **276** | +149 |

Profile: 230 syscalls with binding; 304 without binding (+74: _sysctl, acct, adjtimex, clock_adjtime, clock_nanosleep, clock_settime, copy_file_range, create_module, delete_module, execveat, fanotify_init, fanotify_mark, fchmodat, fchownat, futimesat, get_kernel_syms, getitimer, getpmsg, init_module, ioperm, iopl, lchown, linkat, mkdirat, mknod, mknodat, modify_ldt, msgctl, msgget, msgrcv, msgsnd, nfsservctl, open_by_handle_at, pivot_root, pkey_alloc, pkey_free, pkey_mprotect, preadv, preadv2, process_vm_readv, process_vm_writev, ptrace, putpmsg, pwritev, pwritev2, query_module, quotactl, readahead, reboot, recvmmsg, remap_file_pages, renameat, renameat2, sched_rr_get_interval, semctl, semget, semop, semtimedop, setdomainname, sethostname, settimeofday, swapoff, swapon, symlinkat, sync_file_range, syncfs, syslog, tee, timerfd_gettime, truncate, uselib, ustat, vhangup, vmsplice).

## Eclipse Jetty 9.4.51 (`jetty_9.4.51-jdk8-buster`)

| Library | Bound by | Binding: start functions | Binding: syscalls | No binding: start functions | No binding: syscalls | Only without binding |
|---|---|---:|---:|---:|---:|---|
| libawt.so | JNI | 1 | 0 | 850 | 78 | +78 |
| libj2gss.so | JNI | 1 | 35 | 61 | 35 | +0 |
| libjava.so | JNI | 114 | 84 | 361 | 92 | +8 (chmod, fsync, ftruncate, getegid, getgid, getuid, set_tid_address, umask) |
| libjvm.so | JNI/JVM | 200 | 76 | 30,838 | 92 | +16 |
| libmanagement.so | JNI | 3 | 75 | 119 | 77 | +2 (set_tid_address, times) |
| libnet.so | JNI | 22 | 80 | 181 | 82 | +2 (readv, set_tid_address) |
| libnio.so | JNI | 20 | 80 | 193 | 111 | +31 |
| libzip.so | JNI | 30 | 75 | 213 | 76 | +1 (set_tid_address) |
| libm-2.28.so | imports | 6 | 35 | 907 | 35 | +0 |
| libdl-2.28.so | imports | 6 | 35 | 29 | 35 | +0 |
| libpthread-2.28.so | imports | 60 | 62 | 312 | 79 | +17 |
| libc-2.28.so | imports | 201 | 83 | 3,125 | 273 | +190 |
| ld-linux-x86-64.so.2 | imports | 4 | 25 | 217 | 28 | +3 (access, arch_prctl, brk) |
| **All libraries** | | **668** | **100** | **37,406** | **276** | +176 |

Profile: 161 syscalls with binding; 296 without binding (+135: _sysctl, accept4, acct, adjtimex, alarm, chown, clock_adjtime, clock_nanosleep, clock_settime, copy_file_range, creat, create_module, delete_module, dup3, execveat, faccessat, fallocate, fanotify_init, fanotify_mark, fchmodat, fchownat, fgetxattr, flistxattr, flock, fremovexattr, fsetxattr, futimesat, get_kernel_syms, getcpu, getgroups, getitimer, getpgid, getpmsg, getresgid, getresuid, getsid, getxattr, init_module, inotify_add_watch, inotify_init, inotify_init1, inotify_rm_watch, ioperm, iopl, lchown, lgetxattr, link, linkat, listxattr, llistxattr, lremovexattr, lsetxattr, memfd_create, mkdirat, mknod, mknodat, mlock2, mlockall, modify_ldt, mount, msgctl, msgget, msgrcv, msgsnd, munlockall, name_to_handle_at, nfsservctl, open_by_handle_at, pivot_root, pkey_alloc, pkey_free, pkey_mprotect, ppoll, preadv, preadv2, process_vm_readv, process_vm_writev, ptrace, putpmsg, pwritev, pwritev2, query_module, quotactl, readahead, reboot, recvmmsg, remap_file_pages, removexattr, renameat, renameat2, rt_sigpending, rt_tgsigqueueinfo, sched_rr_get_interval, sched_setparam, select, semctl, semget, semop, semtimedop, sendfile, sendmsg, setdomainname, setfsgid, setfsuid, sethostname, setns, setpgid, setsid, settimeofday, setxattr, signalfd4, splice, swapoff, swapon, symlink, symlinkat, sync, sync_file_range, syncfs, syslog, tee, timerfd_create, timerfd_gettime, timerfd_settime, truncate, umask, umount2, unshare, uselib, ustat, utime, utimensat, vhangup, vmsplice, waitid).

## Apache Storm 2.4.0 (`storm_2.4.0-jdk8-buster`)

| Library | Bound by | Binding: start functions | Binding: syscalls | No binding: start functions | No binding: syscalls | Only without binding |
|---|---|---:|---:|---:|---:|---|
| libawt.so | JNI | 61 | 75 | 850 | 78 | +3 (getitimer, set_tid_address, setitimer) |
| libawt_headless.so | JNI | 1 | 0 | 93 | 76 | +76 |
| libawt_xawt.so | JNI | 20 | 95 | 778 | 97 | +2 (pipe, set_tid_address) |
| libfontmanager.so | JNI | 285 | 75 | 799 | 76 | +1 (set_tid_address) |
| libj2gss.so | JNI | 3 | 35 | 61 | 35 | +0 |
| libjava.so | JNI | 150 | 87 | 361 | 92 | +5 (getegid, getgid, getuid, set_tid_address, umask) |
| libjvm.so | JNI/JVM | 204 | 76 | 30,838 | 92 | +16 |
| libmanagement.so | JNI | 25 | 75 | 119 | 77 | +2 (set_tid_address, times) |
| libnet.so | JNI | 58 | 80 | 181 | 82 | +2 (readv, set_tid_address) |
| libnetty_transport_native_epoll_x86_64-4.1.30.Final.so = libnetty_transport_native_epoll_x86_64.so | JNI | 124 | 70 | 171 | 71 | +1 (set_tid_address) |
| libnio.so | JNI | 81 | 89 | 193 | 111 | +22 |
| librocksdbjni6329444148818420541.so | JNI | 1,971 | 70 | 8,841 | 80 | +10 (dup2, execve, geteuid, kill, mlock, nanosleep, pipe2, readlink, set_tid_address, wait4) |
| libsctp.so | JNI | 22 | 81 | 47 | 82 | +1 (set_tid_address) |
| libzip.so | JNI | 35 | 75 | 213 | 76 | +1 (set_tid_address) |
| libm-2.28.so | imports | 6 | 35 | 907 | 35 | +0 |
| libdl-2.28.so | imports | 6 | 35 | 29 | 35 | +0 |
| libpthread-2.28.so | imports | 60 | 62 | 312 | 79 | +17 |
| libc-2.28.so | imports | 201 | 83 | 3,125 | 273 | +190 |
| ld-linux-x86-64.so.2 | imports | 4 | 25 | 217 | 28 | +3 (access, arch_prctl, brk) |
| **All libraries** | | **3,317** | **133** | **48,135** | **277** | +144 |

Profile: 179 syscalls with binding; 290 without binding (+111: _sysctl, acct, adjtimex, clock_adjtime, clock_nanosleep, clock_settime, copy_file_range, creat, create_module, delete_module, dup3, execveat, fanotify_init, fanotify_mark, fchmodat, fchownat, fgetxattr, flistxattr, fremovexattr, fsetxattr, futimesat, get_kernel_syms, getitimer, getpmsg, getxattr, init_module, inotify_add_watch, inotify_init, inotify_init1, inotify_rm_watch, ioperm, iopl, lchown, lgetxattr, link, linkat, listxattr, llistxattr, lremovexattr, lsetxattr, memfd_create, mkdirat, mknod, mknodat, mlockall, modify_ldt, mount, msgctl, msgget, msgrcv, msgsnd, munlockall, name_to_handle_at, nfsservctl, open_by_handle_at, pivot_root, pkey_alloc, pkey_free, pkey_mprotect, ppoll, preadv, preadv2, process_vm_readv, process_vm_writev, ptrace, putpmsg, pwritev, pwritev2, query_module, quotactl, reboot, recvmmsg, remap_file_pages, removexattr, renameat, renameat2, rt_sigqueueinfo, rt_tgsigqueueinfo, sched_rr_get_interval, sched_setparam, semctl, semget, semop, semtimedop, setdomainname, setfsgid, setfsuid, sethostname, setns, settimeofday, setxattr, signalfd4, swapoff, swapon, symlink, symlinkat, sync, syncfs, syslog, tee, timerfd_gettime, truncate, umount2, unshare, uselib, ustat, utime, utimensat, vhangup, vmsplice, waitid).

## OrientDB 3.2.19 (`orientdb_3.2.19-jdk8-buster`)

| Library | Bound by | Binding: start functions | Binding: syscalls | No binding: start functions | No binding: syscalls | Only without binding |
|---|---|---:|---:|---:|---:|---|
| libNativePosixUtil.so | JNI | 5 | 37 | 22 | 37 | +0 |
| libawt.so | JNI | 16 | 75 | 850 | 78 | +3 (getitimer, set_tid_address, setitimer) |
| libawt_headless.so | JNI | 1 | 0 | 93 | 76 | +76 |
| libawt_xawt.so | JNI | 2 | 95 | 778 | 97 | +2 (pipe, set_tid_address) |
| libfontmanager.so | JNI | 263 | 75 | 799 | 76 | +1 (set_tid_address) |
| libicmp_helper.so | JNI | 1 | 36 | 7 | 36 | +0 |
| libj2gss.so | JNI | 1 | 35 | 61 | 35 | +0 |
| libjava.so | JNI | 143 | 86 | 361 | 92 | +6 (ftruncate, getegid, getgid, getuid, set_tid_address, umask) |
| libjffi-1.2.so | JNI | 157 | 35 | 218 | 35 | +0 |
| libjpeg.so | JNI | 15 | 75 | 309 | 76 | +1 (set_tid_address) |
| libjvm.so | JNI/JVM | 203 | 76 | 30,838 | 92 | +16 |
| liblz4-java-7776228697999496578.so = liblz4-java.so | JNI | 19 | 35 | 129 | 35 | +0 |
| libmanagement.so | JNI | 29 | 75 | 119 | 77 | +2 (set_tid_address, times) |
| libnet.so | JNI | 35 | 80 | 181 | 82 | +2 (readv, set_tid_address) |
| libnio.so | JNI | 25 | 81 | 193 | 111 | +30 |
| libsunec.so | JNI | 38 | 35 | 414 | 35 | +0 |
| libzip.so | JNI | 32 | 75 | 213 | 76 | +1 (set_tid_address) |
| libm-2.28.so | imports | 6 | 35 | 907 | 35 | +0 |
| libdl-2.28.so | imports | 6 | 35 | 29 | 35 | +0 |
| libpthread-2.28.so | imports | 60 | 62 | 312 | 79 | +17 |
| libc-2.28.so | imports | 201 | 83 | 3,125 | 273 | +190 |
| ld-linux-x86-64.so.2 | imports | 4 | 25 | 217 | 28 | +3 (access, arch_prctl, brk) |
| libjffi-1.2.so (supplied) | supplied | 38 | 35 | 308 | 40 | +5 (ftruncate, gettimeofday, mkdir, statfs, unlink) |
| **All libraries** | | **1,300** | **115** | **40,483** | **276** | +161 |

Profile: 174 syscalls with binding; 296 without binding (+122: _sysctl, accept4, acct, adjtimex, alarm, chown, clock_adjtime, clock_nanosleep, clock_settime, copy_file_range, creat, create_module, delete_module, dup3, execveat, fallocate, fanotify_init, fanotify_mark, fchmodat, fchownat, fgetxattr, flistxattr, fremovexattr, fsetxattr, futimesat, get_kernel_syms, getcpu, getitimer, getpmsg, getxattr, init_module, inotify_add_watch, inotify_init, inotify_init1, inotify_rm_watch, ioperm, iopl, lchown, lgetxattr, link, linkat, listxattr, llistxattr, lremovexattr, lsetxattr, memfd_create, mkdirat, mknod, mknodat, mlock2, mlockall, modify_ldt, mount, msgctl, msgget, msgrcv, msgsnd, munlockall, name_to_handle_at, nfsservctl, open_by_handle_at, pivot_root, pkey_alloc, pkey_free, pkey_mprotect, ppoll, preadv, preadv2, process_vm_readv, process_vm_writev, ptrace, putpmsg, pwritev, pwritev2, query_module, quotactl, readahead, reboot, recvmmsg, remap_file_pages, removexattr, renameat, renameat2, rt_tgsigqueueinfo, sched_rr_get_interval, sched_setparam, semctl, semget, semop, semtimedop, setdomainname, setfsgid, setfsuid, sethostname, setns, setsid, settimeofday, setxattr, signalfd4, splice, swapoff, swapon, symlink, symlinkat, sync, sync_file_range, syncfs, syslog, tee, timerfd_create, timerfd_gettime, timerfd_settime, truncate, umount2, unshare, uselib, ustat, utime, utimensat, vhangup, vmsplice, waitid).

## Elasticsearch 7.5.2 (`elasticsearch_7.5.2-jdk8-buster`)

| Library | Bound by | Binding: start functions | Binding: syscalls | No binding: start functions | No binding: syscalls | Only without binding |
|---|---|---:|---:|---:|---:|---|
| libNativePosixUtil.so | JNI | 5 | 37 | 22 | 37 | +0 |
| libawt.so | JNI | 19 | 75 | 850 | 78 | +3 (getitimer, set_tid_address, setitimer) |
| libawt_headless.so | JNI | 1 | 0 | 93 | 76 | +76 |
| libawt_xawt.so | JNI | 14 | 95 | 778 | 97 | +2 (pipe, set_tid_address) |
| libc-2.28.so | JNI, JNA, imports | 203 | 85 | 3,125 | 273 | +188 |
| libfontmanager.so | JNI | 263 | 75 | 799 | 76 | +1 (set_tid_address) |
| libj2gss.so | JNI | 3 | 35 | 61 | 35 | +0 |
| libjava.so | JNI | 143 | 88 | 361 | 92 | +4 (chmod, fsync, set_tid_address, umask) |
| libjnidispatch.so | JNI | 70 | 35 | 125 | 35 | +0 |
| libjvm.so | JNI/JVM | 203 | 76 | 30,838 | 92 | +16 |
| libmanagement.so | JNI | 26 | 75 | 119 | 77 | +2 (set_tid_address, times) |
| libnet.so | JNI | 59 | 80 | 181 | 82 | +2 (readv, set_tid_address) |
| libnio.so | JNI | 75 | 88 | 193 | 111 | +23 |
| libsunec.so | JNI | 38 | 35 | 414 | 35 | +0 |
| libzip.so | JNI | 35 | 75 | 213 | 76 | +1 (set_tid_address) |
| libm-2.28.so | imports | 6 | 35 | 907 | 35 | +0 |
| libdl-2.28.so | imports | 6 | 35 | 29 | 35 | +0 |
| libpthread-2.28.so | imports | 60 | 62 | 312 | 79 | +17 |
| ld-linux-x86-64.so.2 | imports | 4 | 25 | 217 | 28 | +3 (access, arch_prctl, brk) |
| **All libraries** | | **1,233** | **118** | **39,637** | **276** | +158 |

Profile: 185 syscalls with binding; 296 without binding (+111: _sysctl, accept4, acct, adjtimex, clock_adjtime, clock_nanosleep, clock_settime, copy_file_range, creat, create_module, delete_module, dup3, execveat, fallocate, fanotify_init, fanotify_mark, fchmodat, fchownat, fgetxattr, flistxattr, fremovexattr, fsetxattr, futimesat, get_kernel_syms, getcpu, getitimer, getpmsg, getxattr, init_module, inotify_add_watch, inotify_init, inotify_init1, inotify_rm_watch, ioperm, iopl, lchown, lgetxattr, linkat, listxattr, llistxattr, lremovexattr, lsetxattr, memfd_create, mkdirat, mknodat, mlock2, modify_ldt, mount, msgctl, msgget, msgrcv, msgsnd, munlockall, name_to_handle_at, nfsservctl, open_by_handle_at, pivot_root, pkey_alloc, pkey_free, pkey_mprotect, ppoll, preadv, preadv2, process_vm_readv, process_vm_writev, ptrace, putpmsg, pwritev, pwritev2, query_module, quotactl, readahead, reboot, recvmmsg, remap_file_pages, removexattr, renameat, renameat2, rt_tgsigqueueinfo, sched_rr_get_interval, semctl, semget, semop, semtimedop, setdomainname, setfsgid, setfsuid, sethostname, setns, settimeofday, setxattr, signalfd4, swapoff, swapon, symlinkat, sync, sync_file_range, syncfs, syslog, tee, timerfd_create, timerfd_gettime, timerfd_settime, umount2, unshare, uselib, ustat, utimensat, vhangup, vmsplice, waitid).

## Apache Solr 8.7.0 (`solr_8.7.0-jdk8-buster`)

| Library | Bound by | Binding: start functions | Binding: syscalls | No binding: start functions | No binding: syscalls | Only without binding |
|---|---|---:|---:|---:|---:|---|
| libNativePosixUtil.so | JNI | 5 | 37 | 22 | 37 | +0 |
| libawt.so | JNI | 63 | 75 | 850 | 78 | +3 (getitimer, set_tid_address, setitimer) |
| libawt_headless.so | JNI | 1 | 0 | 93 | 76 | +76 |
| libawt_xawt.so | JNI | 18 | 95 | 778 | 97 | +2 (pipe, set_tid_address) |
| libfontmanager.so | JNI | 285 | 75 | 799 | 76 | +1 (set_tid_address) |
| libhadoop-3.3.6.so | JNI | 14 | 41 | 215 | 65 | +24 |
| libhadoop.so | JNI | 125 | 64 | 234 | 64 | +0 |
| libj2gss.so | JNI | 3 | 35 | 61 | 35 | +0 |
| libjava.so | JNI | 166 | 87 | 361 | 92 | +5 (getegid, getgid, getuid, set_tid_address, umask) |
| libjpeg.so | JNI | 16 | 75 | 309 | 76 | +1 (set_tid_address) |
| libjvm.so | JNI/JVM | 205 | 76 | 30,838 | 92 | +16 |
| libmanagement.so | JNI | 31 | 75 | 119 | 77 | +2 (set_tid_address, times) |
| libnet.so | JNI | 62 | 80 | 181 | 82 | +2 (readv, set_tid_address) |
| libnetty_transport_native_epoll_x86_64.so | JNI | 141 | 71 | 194 | 72 | +1 (set_tid_address) |
| libnio.so | JNI | 82 | 89 | 193 | 111 | +22 |
| libsnappyjava.so | JNI | 19 | 35 | 773 | 35 | +0 |
| libsunec.so | JNI | 38 | 35 | 414 | 35 | +0 |
| libzip.so | JNI | 35 | 75 | 213 | 76 | +1 (set_tid_address) |
| libm-2.28.so | imports | 6 | 35 | 907 | 35 | +0 |
| libdl-2.28.so | imports | 6 | 35 | 29 | 35 | +0 |
| libpthread-2.28.so | imports | 60 | 62 | 312 | 79 | +17 |
| libc-2.28.so | imports | 201 | 83 | 3,125 | 273 | +190 |
| ld-linux-x86-64.so.2 | imports | 4 | 25 | 217 | 28 | +3 (access, arch_prctl, brk) |
| **All libraries** | | **1,586** | **131** | **41,237** | **276** | +145 |

Profile: 201 syscalls with binding; 291 without binding (+90: _sysctl, acct, adjtimex, clock_adjtime, clock_nanosleep, clock_settime, copy_file_range, creat, create_module, delete_module, dup3, execveat, fanotify_init, fanotify_mark, fchmodat, fchownat, futimesat, get_kernel_syms, getcpu, getitimer, getpmsg, init_module, inotify_init, ioperm, iopl, linkat, mkdirat, mknod, mknodat, mlock2, mlockall, modify_ldt, msgctl, msgget, msgrcv, msgsnd, munlockall, nfsservctl, open_by_handle_at, pivot_root, pkey_alloc, pkey_free, pkey_mprotect, preadv, preadv2, process_vm_readv, process_vm_writev, ptrace, putpmsg, pwritev, pwritev2, query_module, quotactl, readahead, reboot, remap_file_pages, renameat, renameat2, rt_sigqueueinfo, rt_sigtimedwait, rt_tgsigqueueinfo, sched_rr_get_interval, sched_setparam, semctl, semget, semop, semtimedop, setdomainname, setfsgid, setfsuid, sethostname, setsid, settimeofday, swapoff, swapon, symlink, symlinkat, sync, syncfs, syslog, tee, timerfd_gettime, truncate, unshare, uselib, ustat, utime, utimensat, vhangup, vmsplice).

## Apache Groovy 4.0.0 (`groovy_4.0.0-jdk8-buster`)

| Library | Bound by | Binding: start functions | Binding: syscalls | No binding: start functions | No binding: syscalls | Only without binding |
|---|---|---:|---:|---:|---:|---|
| libattach.so | JNI | 10 | 76 | 21 | 77 | +1 (set_tid_address) |
| libawt.so | JNI | 65 | 75 | 850 | 78 | +3 (getitimer, set_tid_address, setitimer) |
| libawt_headless.so | JNI | 1 | 0 | 93 | 76 | +76 |
| libawt_xawt.so | JNI | 22 | 95 | 778 | 97 | +2 (pipe, set_tid_address) |
| libfontmanager.so | JNI | 284 | 75 | 799 | 76 | +1 (set_tid_address) |
| libjansi-2.14.6.so | JNI | 1 | 36 | 25 | 36 | +0 |
| libjansi.so | JNI | 10 | 36 | 35 | 36 | +0 |
| libjava.so | JNI | 142 | 87 | 361 | 92 | +5 (fsync, getegid, getgid, set_tid_address, umask) |
| libjpeg.so | JNI | 6 | 75 | 309 | 76 | +1 (set_tid_address) |
| libjsound.so | JNI | 3 | 75 | 13 | 76 | +1 (set_tid_address) |
| libjvm.so | JNI/JVM | 209 | 76 | 30,838 | 92 | +16 |
| libmanagement.so | JNI | 8 | 75 | 119 | 77 | +2 (set_tid_address, times) |
| libnet.so | JNI | 30 | 80 | 181 | 82 | +2 (readv, set_tid_address) |
| libnio.so | JNI | 22 | 80 | 193 | 111 | +31 |
| libzip.so | JNI | 33 | 75 | 213 | 76 | +1 (set_tid_address) |
| libm-2.28.so | imports | 6 | 35 | 907 | 35 | +0 |
| libdl-2.28.so | imports | 6 | 35 | 29 | 35 | +0 |
| libpthread-2.28.so | imports | 60 | 62 | 312 | 79 | +17 |
| libc-2.28.so | imports | 201 | 83 | 3,125 | 273 | +190 |
| ld-linux-x86-64.so.2 | imports | 4 | 25 | 217 | 28 | +3 (access, arch_prctl, brk) |
| **All libraries** | | **1,123** | **113** | **39,418** | **276** | +163 |

Profile: 189 syscalls with binding; 296 without binding (+107: _sysctl, accept4, acct, adjtimex, clock_adjtime, clock_nanosleep, clock_settime, copy_file_range, creat, create_module, delete_module, dup3, execveat, fallocate, fanotify_init, fanotify_mark, fchmodat, fchownat, futimesat, get_kernel_syms, getcpu, getitimer, getpmsg, init_module, inotify_add_watch, inotify_init, inotify_init1, inotify_rm_watch, ioperm, iopl, lchown, link, linkat, memfd_create, mkdirat, mknod, mknodat, mlock2, mlockall, modify_ldt, msgctl, msgget, msgrcv, msgsnd, munlockall, name_to_handle_at, nfsservctl, open_by_handle_at, pivot_root, pkey_alloc, pkey_free, pkey_mprotect, ppoll, preadv, preadv2, process_vm_readv, process_vm_writev, ptrace, putpmsg, pwritev, pwritev2, query_module, quotactl, readahead, reboot, recvmmsg, remap_file_pages, renameat, renameat2, rt_tgsigqueueinfo, sched_rr_get_interval, sched_setparam, semctl, semget, semop, semtimedop, sendfile, setdomainname, setfsgid, setfsuid, sethostname, setns, setsid, settimeofday, signalfd4, splice, swapoff, swapon, symlink, symlinkat, sync, sync_file_range, syncfs, syslog, tee, timerfd_create, timerfd_gettime, timerfd_settime, truncate, unshare, uselib, ustat, utime, utimensat, vhangup, vmsplice, waitid).

## JRuby 9.4.2.0 (`jruby_9.4.2.0-jdk8-buster`)

| Library | Bound by | Binding: start functions | Binding: syscalls | No binding: start functions | No binding: syscalls | Only without binding |
|---|---|---:|---:|---:|---:|---|
| libjava.so | JNI | 130 | 85 | 361 | 92 | +7 (fsync, ftruncate, getegid, getgid, getuid, set_tid_address, umask) |
| libjffi-1.2.so | JNI | 195 | 39 | 315 | 41 | +2 (ftruncate, statfs) |
| libjvm.so | JNI/JVM | 200 | 76 | 30,838 | 92 | +16 |
| libmanagement.so | JNI | 16 | 75 | 119 | 77 | +2 (set_tid_address, times) |
| libnet.so | JNI | 37 | 79 | 181 | 82 | +3 (accept, readv, set_tid_address) |
| libnio.so | JNI | 26 | 82 | 193 | 111 | +29 |
| libzip.so | JNI | 26 | 75 | 213 | 76 | +1 (set_tid_address) |
| libm-2.28.so | imports | 6 | 35 | 907 | 35 | +0 |
| libdl-2.28.so | imports | 6 | 35 | 29 | 35 | +0 |
| libpthread-2.28.so | imports | 60 | 62 | 312 | 79 | +17 |
| libc-2.28.so | imports, JNR-FFI | 204 | 86 | 3,125 | 273 | +187 |
| ld-linux-x86-64.so.2 | imports | 4 | 25 | 217 | 28 | +3 (access, arch_prctl, brk) |
| **All libraries** | | **910** | **104** | **36,810** | **276** | +172 |

Profile: 168 syscalls with binding; 296 without binding (+128: _sysctl, accept4, acct, adjtimex, alarm, chown, clock_adjtime, clock_nanosleep, clock_settime, copy_file_range, creat, create_module, delete_module, dup3, execveat, fallocate, fanotify_init, fanotify_mark, fchmodat, fchownat, fgetxattr, flistxattr, flock, fremovexattr, fsetxattr, futimesat, get_kernel_syms, getcpu, getitimer, getpgid, getpmsg, getresgid, getresuid, getsid, getxattr, init_module, inotify_add_watch, inotify_init, inotify_init1, inotify_rm_watch, ioperm, iopl, lchown, lgetxattr, link, linkat, listxattr, llistxattr, lremovexattr, lsetxattr, mkdirat, mknod, mknodat, mlock2, mlockall, modify_ldt, mount, msgctl, msgget, msgrcv, msgsnd, munlockall, name_to_handle_at, nfsservctl, open_by_handle_at, pivot_root, pkey_alloc, pkey_free, pkey_mprotect, ppoll, preadv, preadv2, process_vm_readv, process_vm_writev, ptrace, putpmsg, pwritev, pwritev2, query_module, quotactl, readahead, reboot, recvmmsg, remap_file_pages, removexattr, renameat, renameat2, rt_sigpending, rt_tgsigqueueinfo, sched_rr_get_interval, sched_setparam, select, semctl, semget, semop, semtimedop, sendmsg, setdomainname, setfsgid, setfsuid, sethostname, setns, setsid, settimeofday, setxattr, signalfd4, swapoff, swapon, symlink, symlinkat, sync, sync_file_range, syncfs, syslog, tee, timerfd_create, timerfd_gettime, timerfd_settime, truncate, umount2, unshare, uselib, ustat, utime, utimensat, vhangup, vmsplice, waitid).
