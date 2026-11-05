# Added binaries (not captured)

- `cat` — added 2026-11-05 ~18:00 (user decision "Analyse cp, rerun 9-11", applied to storm's `cat`).
  storm's /docker-entrypoint.sh writes storm.yaml with `cat << EOF > "$CONFIG"` only when the file does
  not exist (first start). sysdig_unified.sh captures a `docker stop` + `docker start` of the
  already-initialised container, so this branch never runs during capture and `cat` is missing from
  binaries_unique; the fresh stage-11 verify container does run it.
  Source: /usr/bin/cat copied from image storm:2.8.8 (docker create + docker cp -L),
  Build ID 3d35b26ede5ed84094cb43b61d3b9f01b9ff41f7, debug symbols from debuginfod.ubuntu.com (Build-ID
  verified), merged with eu-unstrip + objcopy --strip-debug like every other binary. Analysed with the
  same SysPart build and start-function rule as the other executables (stage 7 binaries phase).
  Note: in storm:2.8.8 (Ubuntu, uutils/rust coreutils) /usr/bin/cat -> /usr/lib/cargo/bin/coreutils/cat
  is a hardlink of the single multi-call coreutils binary (115 links) that the captured chown, cut,
  dirname, env and id already are; its SysPart result is therefore expected to equal theirs.

# Multi-call binary: per-tool uumain start (2026-11-05 ~21:00)

storm:2.8.8's coreutils (cat, chown, cut, dirname, env, id) are symlinks/hardlinks to ONE uutils multi-call
binary (Build ID 3d35b26e...) that dispatches on argv[0] through a function table SysPart does not follow.
Analysed from `_start` alone, every tool got the same 43 startup syscalls (stage 11 then failed: chown -R
needs fchownat). Each tool was rerun with starts `_start` + its own `uu_<tool>::uumain` (same SysPart build,
same wrapper); the `_start`-only results are kept in Binary_Analysis_before_uumain/.

# Executables: _start + main start functions (2026-11-05 22:57)

storm_2.8.8: python3.14 were rerun with starts `_start` + `main` (plus `uu_<tool>::uumain` for uutils
multi-call binaries), the rule automate_syscall_analysis.sh now applies to every dynamically linked
executable. In non-PIE binaries _start hands main to __libc_start_main as an absolute immediate that
SysPart does not follow, so analysed from `_start` alone they only got libc's startup syscalls.
Previous results are kept in Binary_Analysis_before_main/.
