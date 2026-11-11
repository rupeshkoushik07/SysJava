# Binding vs no binding: all ten JDK 8 images (static analysis only)

Binding = SysPart from the functions the native methods map to (the pipeline's own run). No binding = SysPart from every function in the library (same file, same SysPart build). All images: JDK 8u504 (Eclipse Temurin), Debian 10. libjvm.so without binding is not resolved (out of memory at 35 and 60 GB on Tomcat 11), so the "All except libjvm.so" rows leave it out; for the profile column libjvm keeps its binding set.

| Image | Libraries | Binding: start functions | Binding: syscalls | No binding: start functions | No binding: syscalls | Profile with binding | Profile without binding | Added to profile |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Apache Cassandra 3.0.29 | 17 | 1,012 | 124 | 8,261 | 275 | 230 | 304 | +74 (_sysctl, acct, adjtimex, clock_adjtime, clock_nanosleep, clock_settime, copy_file_range, create_module, delete_module, execveat, fanotify_init, fanotify_mark, fchmodat, fchownat, futimesat, get_kernel_syms, getitimer, getpmsg, init_module, ioperm, iopl, lchown, linkat, mkdirat, mknod, mknodat, modify_ldt, msgctl, msgget, msgrcv, msgsnd, nfsservctl, open_by_handle_at, pivot_root, pkey_alloc, pkey_free, pkey_mprotect, preadv, preadv2, process_vm_readv, process_vm_writev, ptrace, putpmsg, pwritev, pwritev2, query_module, quotactl, readahead, reboot, recvmmsg, remap_file_pages, renameat, renameat2, sched_rr_get_interval, semctl, semget, semop, semtimedop, setdomainname, sethostname, settimeofday, swapoff, swapon, symlinkat, sync_file_range, syncfs, syslog, tee, timerfd_gettime, truncate, uselib, ustat, vhangup, vmsplice) |
| Elasticsearch 7.5.2 | 15 | 756 | 112 | 7,334 | 275 | 185 | 295 | +110 (_sysctl, accept4, acct, adjtimex, clock_adjtime, clock_nanosleep, clock_settime, copy_file_range, creat, create_module, delete_module, dup3, execveat, fallocate, fanotify_init, fanotify_mark, fchmodat, fchownat, fgetxattr, flistxattr, fremovexattr, fsetxattr, futimesat, get_kernel_syms, getcpu, getitimer, getpmsg, getxattr, init_module, inotify_add_watch, inotify_init, inotify_init1, inotify_rm_watch, ioperm, iopl, lchown, lgetxattr, linkat, listxattr, llistxattr, lremovexattr, lsetxattr, memfd_create, mkdirat, mknodat, mlock2, modify_ldt, mount, msgctl, msgget, msgrcv, msgsnd, munlockall, name_to_handle_at, nfsservctl, open_by_handle_at, pivot_root, pkey_alloc, pkey_free, pkey_mprotect, ppoll, preadv, preadv2, process_vm_readv, process_vm_writev, ptrace, putpmsg, pwritev, pwritev2, query_module, quotactl, readahead, reboot, recvmmsg, remap_file_pages, removexattr, renameat, renameat2, sched_rr_get_interval, semctl, semget, semop, semtimedop, setdomainname, setfsgid, setfsuid, sethostname, setns, settimeofday, setxattr, signalfd4, swapoff, swapon, symlinkat, sync, sync_file_range, syncfs, syslog, tee, timerfd_create, timerfd_gettime, timerfd_settime, umount2, unshare, uselib, ustat, utimensat, vhangup, vmsplice, waitid) |
| Apache Groovy 4.0.0 | 15 | 637 | 109 | 3,990 | 128 | 189 | 198 | +9 (getitimer, inotify_add_watch, inotify_init, inotify_rm_watch, lchown, link, mknod, sendfile, symlink) |
| Eclipse Jetty 9.4.51 | 8 | 191 | 92 | 1,978 | 120 | 161 | 173 | +12 (chown, getitimer, inotify_add_watch, inotify_init, inotify_rm_watch, lchown, link, mknod, sendfile, sendmsg, symlink, umask) |
| JRuby 9.4.2.0 | 7 | 430 | 95 | 1,382 | 119 | 168 | 177 | +9 (chown, inotify_add_watch, inotify_init, inotify_rm_watch, lchown, link, mknod, sendmsg, symlink) |
| OrientDB 3.2.19 | 17 | 782 | 111 | 4,747 | 129 | 174 | 183 | +9 (chown, getitimer, inotify_add_watch, inotify_init, inotify_rm_watch, lchown, link, mknod, symlink) |
| Apache Solr 8.7.0 | 18 | 1,104 | 127 | 5,809 | 140 | 201 | 205 | +4 (getitimer, inotify_init, mknod, symlink) |
| Apache Storm 2.4.0 | 14 | 2,836 | 129 | 12,707 | 144 | 179 | 187 | +8 (getitimer, inotify_add_watch, inotify_init, inotify_rm_watch, lchown, link, mknod, symlink) |
| Apache Tomcat 7.0.109 | 14 | 925 | 124 | 4,686 | 138 | 173 | 180 | +7 (getitimer, inotify_add_watch, inotify_init, inotify_rm_watch, lchown, mknod, symlink) |
| Apache ZooKeeper 3.4.14 | 11 | 590 | 108 | 3,648 | 128 | 192 | 201 | +9 (getitimer, inotify_add_watch, inotify_init, inotify_rm_watch, lchown, link, mknod, symlink, utimes) |
| **Mean** | | | | | | **185.2** | **210.3** | +25.1 |

Syscalls added to the profile without binding, by number of images: `getitimer` (9), `inotify_init` (9), `lchown` (9), `mknod` (9), `inotify_add_watch` (8), `inotify_rm_watch` (8), `symlink` (8), `link` (6), `chown` (3), `_sysctl` (2), `acct` (2), `adjtimex` (2), `clock_adjtime` (2), `clock_nanosleep` (2), `clock_settime` (2), `copy_file_range` (2), `create_module` (2), `delete_module` (2), `execveat` (2), `fanotify_init` (2), `fanotify_mark` (2), `fchmodat` (2), `fchownat` (2), `futimesat` (2), `get_kernel_syms` (2), `getpmsg` (2), `init_module` (2), `ioperm` (2), `iopl` (2), `linkat` (2), `mkdirat` (2), `mknodat` (2), `modify_ldt` (2), `msgctl` (2), `msgget` (2), `msgrcv` (2), `msgsnd` (2), `nfsservctl` (2), `open_by_handle_at` (2), `pivot_root` (2), `pkey_alloc` (2), `pkey_free` (2), `pkey_mprotect` (2), `preadv` (2), `preadv2` (2), `process_vm_readv` (2), `process_vm_writev` (2), `ptrace` (2), `putpmsg` (2), `pwritev` (2), `pwritev2` (2), `query_module` (2), `quotactl` (2), `readahead` (2), `reboot` (2), `recvmmsg` (2), `remap_file_pages` (2), `renameat` (2), `renameat2` (2), `sched_rr_get_interval` (2), `semctl` (2), `semget` (2), `semop` (2), `semtimedop` (2), `sendfile` (2), `sendmsg` (2), `setdomainname` (2), `sethostname` (2), `settimeofday` (2), `swapoff` (2), `swapon` (2), `symlinkat` (2), `sync_file_range` (2), `syncfs` (2), `syslog` (2), `tee` (2), `timerfd_gettime` (2), `uselib` (2), `ustat` (2), `vhangup` (2), `vmsplice` (2), `accept4` (1), `creat` (1), `dup3` (1), `fallocate` (1), `fgetxattr` (1), `flistxattr` (1), `fremovexattr` (1), `fsetxattr` (1), `getcpu` (1), `getxattr` (1), `inotify_init1` (1), `lgetxattr` (1), `listxattr` (1), `llistxattr` (1), `lremovexattr` (1), `lsetxattr` (1), `memfd_create` (1), `mlock2` (1), `mount` (1), `munlockall` (1), `name_to_handle_at` (1), `ppoll` (1), `removexattr` (1), `setfsgid` (1), `setfsuid` (1), `setns` (1), `setxattr` (1), `signalfd4` (1), `sync` (1), `timerfd_create` (1), `timerfd_settime` (1), `truncate` (1), `umask` (1), `umount2` (1), `unshare` (1), `utimensat` (1), `utimes` (1), `waitid` (1)

## Apache Cassandra 3.0.29 (`cassandra_3.0.29-jdk8-buster`)

| Library | Binding: start functions | Binding: syscalls | No binding: start functions | No binding: syscalls | Only without binding |
|---|---:|---:|---:|---:|---|
| libawt.so | 62 | 75 | 850 | 78 | +3 (getitimer, set_tid_address, setitimer) |
| libawt_headless.so | 1 | 0 | 93 | 76 | +76 |
| libawt_xawt.so | 18 | 95 | 778 | 97 | +2 (pipe, set_tid_address) |
| libc-2.28.so | 3 | 3 | 3,125 | 273 | +270 |
| libfontmanager.so | 284 | 75 | 799 | 76 | +1 (set_tid_address) |
| libjava.so | 141 | 86 | 361 | 92 | +6 (ftruncate, getegid, getgid, getuid, set_tid_address, umask) |
| libjnidispatch.so | 69 | 35 | 124 | 35 | +0 |
| libjvm.so | 210 | 77 | not resolved | not resolved | |
| liblz4-java.so = liblz4-java1864768816310256501.so = liblz4-java3154006651160629592.so | 19 | 35 | 93 | 35 | +0 |
| libmanagement.so | 26 | 75 | 119 | 77 | +2 (set_tid_address, times) |
| libnet.so | 41 | 80 | 181 | 82 | +2 (readv, set_tid_address) |
| libnetty-transport-native-epoll.so | 107 | 68 | 137 | 69 | +1 (set_tid_address) |
| libnio.so | 40 | 82 | 193 | 111 | +29 |
| libsctp.so | 22 | 81 | 47 | 82 | +1 (set_tid_address) |
| libsigar-amd64-linux.so | 127 | 60 | 427 | 60 | +0 |
| libsnappyjava.so | 15 | 35 | 721 | 35 | +0 |
| libzip.so | 37 | 75 | 213 | 76 | +1 (set_tid_address) |
| **All except libjvm.so** | **1,012** | **124** | **8,261** | **275** | +151 |

Profile: 230 syscalls with binding (final policy); 304 without binding (+74: _sysctl, acct, adjtimex, clock_adjtime, clock_nanosleep, clock_settime, copy_file_range, create_module, delete_module, execveat, fanotify_init, fanotify_mark, fchmodat, fchownat, futimesat, get_kernel_syms, getitimer, getpmsg, init_module, ioperm, iopl, lchown, linkat, mkdirat, mknod, mknodat, modify_ldt, msgctl, msgget, msgrcv, msgsnd, nfsservctl, open_by_handle_at, pivot_root, pkey_alloc, pkey_free, pkey_mprotect, preadv, preadv2, process_vm_readv, process_vm_writev, ptrace, putpmsg, pwritev, pwritev2, query_module, quotactl, readahead, reboot, recvmmsg, remap_file_pages, renameat, renameat2, sched_rr_get_interval, semctl, semget, semop, semtimedop, setdomainname, sethostname, settimeofday, swapoff, swapon, symlinkat, sync_file_range, syncfs, syslog, tee, timerfd_gettime, truncate, uselib, ustat, vhangup, vmsplice).

## Elasticsearch 7.5.2 (`elasticsearch_7.5.2-jdk8-buster`)

| Library | Binding: start functions | Binding: syscalls | No binding: start functions | No binding: syscalls | Only without binding |
|---|---:|---:|---:|---:|---|
| libNativePosixUtil.so | 5 | 37 | 22 | 37 | +0 |
| libawt.so | 19 | 75 | 850 | 78 | +3 (getitimer, set_tid_address, setitimer) |
| libawt_headless.so | 1 | 0 | 93 | 76 | +76 |
| libawt_xawt.so | 14 | 95 | 778 | 97 | +2 (pipe, set_tid_address) |
| libc-2.28.so | 5 | 37 | 3,125 | 273 | +236 |
| libfontmanager.so | 263 | 75 | 799 | 76 | +1 (set_tid_address) |
| libj2gss.so | 3 | 35 | 61 | 35 | +0 |
| libjava.so | 143 | 88 | 361 | 92 | +4 (chmod, fsync, set_tid_address, umask) |
| libjnidispatch.so | 70 | 35 | 125 | 35 | +0 |
| libjvm.so | 203 | 76 | not resolved | not resolved | |
| libmanagement.so | 26 | 75 | 119 | 77 | +2 (set_tid_address, times) |
| libnet.so | 59 | 80 | 181 | 82 | +2 (readv, set_tid_address) |
| libnio.so | 75 | 88 | 193 | 111 | +23 |
| libsunec.so | 38 | 35 | 414 | 35 | +0 |
| libzip.so | 35 | 75 | 213 | 76 | +1 (set_tid_address) |
| **All except libjvm.so** | **756** | **112** | **7,334** | **275** | +163 |

Profile: 185 syscalls with binding (final policy); 295 without binding (+110: _sysctl, accept4, acct, adjtimex, clock_adjtime, clock_nanosleep, clock_settime, copy_file_range, creat, create_module, delete_module, dup3, execveat, fallocate, fanotify_init, fanotify_mark, fchmodat, fchownat, fgetxattr, flistxattr, fremovexattr, fsetxattr, futimesat, get_kernel_syms, getcpu, getitimer, getpmsg, getxattr, init_module, inotify_add_watch, inotify_init, inotify_init1, inotify_rm_watch, ioperm, iopl, lchown, lgetxattr, linkat, listxattr, llistxattr, lremovexattr, lsetxattr, memfd_create, mkdirat, mknodat, mlock2, modify_ldt, mount, msgctl, msgget, msgrcv, msgsnd, munlockall, name_to_handle_at, nfsservctl, open_by_handle_at, pivot_root, pkey_alloc, pkey_free, pkey_mprotect, ppoll, preadv, preadv2, process_vm_readv, process_vm_writev, ptrace, putpmsg, pwritev, pwritev2, query_module, quotactl, readahead, reboot, recvmmsg, remap_file_pages, removexattr, renameat, renameat2, sched_rr_get_interval, semctl, semget, semop, semtimedop, setdomainname, setfsgid, setfsuid, sethostname, setns, settimeofday, setxattr, signalfd4, swapoff, swapon, symlinkat, sync, sync_file_range, syncfs, syslog, tee, timerfd_create, timerfd_gettime, timerfd_settime, umount2, unshare, uselib, ustat, utimensat, vhangup, vmsplice, waitid).

## Apache Groovy 4.0.0 (`groovy_4.0.0-jdk8-buster`)

| Library | Binding: start functions | Binding: syscalls | No binding: start functions | No binding: syscalls | Only without binding |
|---|---:|---:|---:|---:|---|
| libattach.so | 10 | 76 | 21 | 77 | +1 (set_tid_address) |
| libawt.so | 65 | 75 | 850 | 78 | +3 (getitimer, set_tid_address, setitimer) |
| libawt_headless.so | 1 | 0 | 93 | 76 | +76 |
| libawt_xawt.so | 22 | 95 | 778 | 97 | +2 (pipe, set_tid_address) |
| libfontmanager.so | 284 | 75 | 799 | 76 | +1 (set_tid_address) |
| libjansi-2.14.6.so | 1 | 36 | 25 | 36 | +0 |
| libjansi.so | 10 | 36 | 35 | 36 | +0 |
| libjava.so | 142 | 87 | 361 | 92 | +5 (fsync, getegid, getgid, set_tid_address, umask) |
| libjpeg.so | 6 | 75 | 309 | 76 | +1 (set_tid_address) |
| libjsound.so | 3 | 75 | 13 | 76 | +1 (set_tid_address) |
| libjvm.so | 209 | 76 | not resolved | not resolved | |
| libmanagement.so | 8 | 75 | 119 | 77 | +2 (set_tid_address, times) |
| libnet.so | 30 | 80 | 181 | 82 | +2 (readv, set_tid_address) |
| libnio.so | 22 | 80 | 193 | 111 | +31 |
| libzip.so | 33 | 75 | 213 | 76 | +1 (set_tid_address) |
| **All except libjvm.so** | **637** | **109** | **3,990** | **128** | +19 |

Profile: 189 syscalls with binding (final policy); 198 without binding (+9: getitimer, inotify_add_watch, inotify_init, inotify_rm_watch, lchown, link, mknod, sendfile, symlink).

## Eclipse Jetty 9.4.51 (`jetty_9.4.51-jdk8-buster`)

| Library | Binding: start functions | Binding: syscalls | No binding: start functions | No binding: syscalls | Only without binding |
|---|---:|---:|---:|---:|---|
| libawt.so | 1 | 0 | 850 | 78 | +78 |
| libj2gss.so | 1 | 35 | 61 | 35 | +0 |
| libjava.so | 114 | 84 | 361 | 92 | +8 (chmod, fsync, ftruncate, getegid, getgid, getuid, set_tid_address, umask) |
| libjvm.so | 200 | 76 | not resolved | not resolved | |
| libmanagement.so | 3 | 75 | 119 | 77 | +2 (set_tid_address, times) |
| libnet.so | 22 | 80 | 181 | 82 | +2 (readv, set_tid_address) |
| libnio.so | 20 | 80 | 193 | 111 | +31 |
| libzip.so | 30 | 75 | 213 | 76 | +1 (set_tid_address) |
| **All except libjvm.so** | **191** | **92** | **1,978** | **120** | +28 |

Profile: 161 syscalls with binding (final policy); 173 without binding (+12: chown, getitimer, inotify_add_watch, inotify_init, inotify_rm_watch, lchown, link, mknod, sendfile, sendmsg, symlink, umask).

## JRuby 9.4.2.0 (`jruby_9.4.2.0-jdk8-buster`)

| Library | Binding: start functions | Binding: syscalls | No binding: start functions | No binding: syscalls | Only without binding |
|---|---:|---:|---:|---:|---|
| libjava.so | 130 | 85 | 361 | 92 | +7 (fsync, ftruncate, getegid, getgid, getuid, set_tid_address, umask) |
| libjffi-1.2.so | 195 | 39 | 315 | 41 | +2 (ftruncate, statfs) |
| libjvm.so | 200 | 76 | not resolved | not resolved | |
| libmanagement.so | 16 | 75 | 119 | 77 | +2 (set_tid_address, times) |
| libnet.so | 37 | 79 | 181 | 82 | +3 (accept, readv, set_tid_address) |
| libnio.so | 26 | 82 | 193 | 111 | +29 |
| libzip.so | 26 | 75 | 213 | 76 | +1 (set_tid_address) |
| **All except libjvm.so** | **430** | **95** | **1,382** | **119** | +24 |

Profile: 168 syscalls with binding (final policy); 177 without binding (+9: chown, inotify_add_watch, inotify_init, inotify_rm_watch, lchown, link, mknod, sendmsg, symlink).

## OrientDB 3.2.19 (`orientdb_3.2.19-jdk8-buster`)

| Library | Binding: start functions | Binding: syscalls | No binding: start functions | No binding: syscalls | Only without binding |
|---|---:|---:|---:|---:|---|
| libNativePosixUtil.so | 5 | 37 | 22 | 37 | +0 |
| libawt.so | 16 | 75 | 850 | 78 | +3 (getitimer, set_tid_address, setitimer) |
| libawt_headless.so | 1 | 0 | 93 | 76 | +76 |
| libawt_xawt.so | 2 | 95 | 778 | 97 | +2 (pipe, set_tid_address) |
| libfontmanager.so | 263 | 75 | 799 | 76 | +1 (set_tid_address) |
| libicmp_helper.so | 1 | 36 | 7 | 36 | +0 |
| libj2gss.so | 1 | 35 | 61 | 35 | +0 |
| libjava.so | 143 | 86 | 361 | 92 | +6 (ftruncate, getegid, getgid, getuid, set_tid_address, umask) |
| libjffi-1.2.so | 157 | 35 | 218 | 35 | +0 |
| libjpeg.so | 15 | 75 | 309 | 76 | +1 (set_tid_address) |
| libjvm.so | 203 | 76 | not resolved | not resolved | |
| liblz4-java-7776228697999496578.so = liblz4-java.so | 19 | 35 | 129 | 35 | +0 |
| libmanagement.so | 29 | 75 | 119 | 77 | +2 (set_tid_address, times) |
| libnet.so | 35 | 80 | 181 | 82 | +2 (readv, set_tid_address) |
| libnio.so | 25 | 81 | 193 | 111 | +30 |
| libsunec.so | 38 | 35 | 414 | 35 | +0 |
| libzip.so | 32 | 75 | 213 | 76 | +1 (set_tid_address) |
| **All except libjvm.so** | **782** | **111** | **4,747** | **129** | +18 |

Profile: 174 syscalls with binding (final policy); 183 without binding (+9: chown, getitimer, inotify_add_watch, inotify_init, inotify_rm_watch, lchown, link, mknod, symlink).

## Apache Solr 8.7.0 (`solr_8.7.0-jdk8-buster`)

| Library | Binding: start functions | Binding: syscalls | No binding: start functions | No binding: syscalls | Only without binding |
|---|---:|---:|---:|---:|---|
| libNativePosixUtil.so | 5 | 37 | 22 | 37 | +0 |
| libawt.so | 63 | 75 | 850 | 78 | +3 (getitimer, set_tid_address, setitimer) |
| libawt_headless.so | 1 | 0 | 93 | 76 | +76 |
| libawt_xawt.so | 18 | 95 | 778 | 97 | +2 (pipe, set_tid_address) |
| libfontmanager.so | 285 | 75 | 799 | 76 | +1 (set_tid_address) |
| libhadoop-3.3.6.so | 14 | 41 | 215 | 65 | +24 |
| libhadoop.so | 125 | 64 | 234 | 64 | +0 |
| libj2gss.so | 3 | 35 | 61 | 35 | +0 |
| libjava.so | 166 | 87 | 361 | 92 | +5 (getegid, getgid, getuid, set_tid_address, umask) |
| libjpeg.so | 16 | 75 | 309 | 76 | +1 (set_tid_address) |
| libjvm.so | 205 | 76 | not resolved | not resolved | |
| libmanagement.so | 31 | 75 | 119 | 77 | +2 (set_tid_address, times) |
| libnet.so | 62 | 80 | 181 | 82 | +2 (readv, set_tid_address) |
| libnetty_transport_native_epoll_x86_64.so | 141 | 71 | 194 | 72 | +1 (set_tid_address) |
| libnio.so | 82 | 89 | 193 | 111 | +22 |
| libsnappyjava.so | 19 | 35 | 773 | 35 | +0 |
| libsunec.so | 38 | 35 | 414 | 35 | +0 |
| libzip.so | 35 | 75 | 213 | 76 | +1 (set_tid_address) |
| **All except libjvm.so** | **1,104** | **127** | **5,809** | **140** | +13 |

Profile: 201 syscalls with binding (final policy); 205 without binding (+4: getitimer, inotify_init, mknod, symlink).

## Apache Storm 2.4.0 (`storm_2.4.0-jdk8-buster`)

| Library | Binding: start functions | Binding: syscalls | No binding: start functions | No binding: syscalls | Only without binding |
|---|---:|---:|---:|---:|---|
| libawt.so | 61 | 75 | 850 | 78 | +3 (getitimer, set_tid_address, setitimer) |
| libawt_headless.so | 1 | 0 | 93 | 76 | +76 |
| libawt_xawt.so | 20 | 95 | 778 | 97 | +2 (pipe, set_tid_address) |
| libfontmanager.so | 285 | 75 | 799 | 76 | +1 (set_tid_address) |
| libj2gss.so | 3 | 35 | 61 | 35 | +0 |
| libjava.so | 150 | 87 | 361 | 92 | +5 (getegid, getgid, getuid, set_tid_address, umask) |
| libjvm.so | 204 | 76 | not resolved | not resolved | |
| libmanagement.so | 25 | 75 | 119 | 77 | +2 (set_tid_address, times) |
| libnet.so | 58 | 80 | 181 | 82 | +2 (readv, set_tid_address) |
| libnetty_transport_native_epoll_x86_64-4.1.30.Final.so = libnetty_transport_native_epoll_x86_64.so | 124 | 70 | 171 | 71 | +1 (set_tid_address) |
| libnio.so | 81 | 89 | 193 | 111 | +22 |
| librocksdbjni6329444148818420541.so | 1,971 | 70 | 8,841 | 80 | +10 (dup2, execve, geteuid, kill, mlock, nanosleep, pipe2, readlink, set_tid_address, wait4) |
| libsctp.so | 22 | 81 | 47 | 82 | +1 (set_tid_address) |
| libzip.so | 35 | 75 | 213 | 76 | +1 (set_tid_address) |
| **All except libjvm.so** | **2,836** | **129** | **12,707** | **144** | +15 |

Profile: 179 syscalls with binding (final policy); 187 without binding (+8: getitimer, inotify_add_watch, inotify_init, inotify_rm_watch, lchown, link, mknod, symlink).

## Apache Tomcat 7.0.109 (`tomcat_7.0-jdk8-buster`)

| Library | Binding: start functions | Binding: syscalls | No binding: start functions | No binding: syscalls | Only without binding |
|---|---:|---:|---:|---:|---|
| libawt.so | 20 | 75 | 850 | 78 | +3 (getitimer, set_tid_address, setitimer) |
| libawt_headless.so | 1 | 0 | 93 | 76 | +76 |
| libawt_xawt.so | 11 | 95 | 778 | 97 | +2 (pipe, set_tid_address) |
| libfontmanager.so | 263 | 75 | 799 | 76 | +1 (set_tid_address) |
| libj2gss.so | 1 | 35 | 61 | 35 | +0 |
| libj2pkcs11.so | 67 | 35 | 166 | 35 | +0 |
| libjava.so | 136 | 85 | 361 | 92 | +7 (chmod, fsync, getegid, getgid, getuid, set_tid_address, umask) |
| libjvm.so | 202 | 76 | not resolved | not resolved | |
| libmanagement.so | 33 | 75 | 119 | 77 | +2 (set_tid_address, times) |
| libnet.so | 34 | 80 | 181 | 82 | +2 (readv, set_tid_address) |
| libnio.so | 26 | 82 | 193 | 111 | +29 |
| libsunec.so | 38 | 35 | 414 | 35 | +0 |
| libtcnative-1.so.0 = libtcnative-1.so.0.2.28 | 264 | 99 | 458 | 101 | +2 (getppid, set_tid_address) |
| libzip.so | 31 | 75 | 213 | 76 | +1 (set_tid_address) |
| **All except libjvm.so** | **925** | **124** | **4,686** | **138** | +14 |

Profile: 173 syscalls with binding (final policy); 180 without binding (+7: getitimer, inotify_add_watch, inotify_init, inotify_rm_watch, lchown, mknod, symlink).

## Apache ZooKeeper 3.4.14 (`zookeeper_3.4.14-jdk8-buster`)

| Library | Binding: start functions | Binding: syscalls | No binding: start functions | No binding: syscalls | Only without binding |
|---|---:|---:|---:|---:|---|
| libawt.so | 63 | 75 | 850 | 78 | +3 (getitimer, set_tid_address, setitimer) |
| libawt_headless.so | 1 | 0 | 93 | 76 | +76 |
| libawt_xawt.so | 18 | 95 | 778 | 97 | +2 (pipe, set_tid_address) |
| libfontmanager.so | 284 | 75 | 799 | 76 | +1 (set_tid_address) |
| libj2gss.so | 1 | 35 | 61 | 35 | +0 |
| libjava.so | 117 | 84 | 361 | 92 | +8 (chmod, fsync, getegid, getgid, getuid, set_tid_address, umask, utimes) |
| libjvm.so | 198 | 76 | not resolved | not resolved | |
| libmanagement.so | 13 | 75 | 119 | 77 | +2 (set_tid_address, times) |
| libnet.so | 37 | 80 | 181 | 82 | +2 (readv, set_tid_address) |
| libnio.so | 22 | 81 | 193 | 111 | +30 |
| libzip.so | 34 | 75 | 213 | 76 | +1 (set_tid_address) |
| **All except libjvm.so** | **590** | **108** | **3,648** | **128** | +20 |

Profile: 192 syscalls with binding (final policy); 201 without binding (+9: getitimer, inotify_add_watch, inotify_init, inotify_rm_watch, lchown, link, mknod, symlink, utimes).
