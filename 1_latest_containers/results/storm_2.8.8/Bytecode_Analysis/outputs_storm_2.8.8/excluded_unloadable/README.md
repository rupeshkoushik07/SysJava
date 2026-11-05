# Excluded: netty io_uring native library (unloadable in storm_2.8.8)

User decision 2026-11-05 ("Yes, drop it"), relayed by the coordinator session: both start files below
are excluded from SysPart and from the seccomp merge.

- `libnetty_transport_native_io_uring42_x86_64.so.txt` (84 starts)
- `libnetty_transport_native_io_uring42_x86_64-4.2.12.Final.so.txt` (160 starts; the .so is a symlink alias of the same library)

Reason: storm-shaded-deps-2.8.8.jar renames netty's epoll and tcnative natives to
`liborg_apache_storm_shade_netty_*`, but its io_uring native keeps the unshaded `libnetty_*` name.
The shaded classes ask for `liborg_apache_storm_shade_netty_transport_native_io_uring42_x86_64.so`,
which does not exist, so storm cannot load io_uring. The copy in LIBS_storm_2.8.8 was extracted from
the jar, not captured at runtime (sysdig_outputs_storm_2.8.8/jni_libs_opened.txt has no netty library),
so stage 8 does not treat it as an unanalysed loaded library either. Details:
EchoTrace_latest/unavailable_libs/NOTES.md, section "Previous-run comparison".

Mechanism: stage 7 had already listed all 22 start files when this was decided (it was at item 8/22).
The files were moved here with a `.excluded` suffix (so a future `find -name '*.so.txt'` does not pick
them up again), and compute_syscalls_lowmem.sh exits 4 without running SysPart when a start file is
missing, so those two items fail fast and produce no syscalls.
