# SysPart

SysJava uses SysPart for the binary call-graph analysis. SysPart is a
third-party tool built on the Egalito binary recompiler. Every result in this
artifact uses one pinned build, described in [`PINNED.md`](PINNED.md):

| | |
|---|---|
| SysPartCode | https://github.com/vidyalakshmir/SysPartCode @ `453694d9e16e6348cd8b1471321ee538fa02c416` + `syspart-app-local.patch` |
| Egalito | https://github.com/stevens-s3lab/egalito @ `8f94390ea06ee90c499705013a42bec41abb4b7b` + `egalito-local.patch` |
| `syspart` md5 | `3618898bddb178963302e573fee69c97` |

## Build

Tested on Ubuntu 22.04. Prerequisites as in SysPartCode's README
(`make g++ libreadline-dev gdb lsb-release unzip libc6-dbg`).

```bash
ART=/path/to/artifact
git clone https://github.com/vidyalakshmir/SysPartCode.git && cd SysPartCode
git checkout 453694d9e16e6348cd8b1471321ee538fa02c416
git apply "$ART/syspart/syspart-app-local.patch"
git submodule update --init analysis/tools/egalito
# Do NOT run build_upgraded_egalito.sh: it checks out and pulls a moving branch.
cd analysis/tools/egalito
git fetch origin && git checkout 8f94390ea06ee90c499705013a42bec41abb4b7b
git submodule update --init --recursive
git apply "$ART/syspart/egalito-local.patch"
make -j"$(nproc)"
cd ../../app && make
ls build_x86_64/syspart                    # must exist
export SYSPART_ROOT="$(cd ../.. && pwd)"
```

Your binary's md5 can differ from the pinned one: compiler versions change the
bytes but not the analysis.

## Local patches

* `egalito-local.patch` skips an unresolved lazy PLT entry and an unresolved
  library instead of dereferencing a null pointer. This crash occurs on stripped
  glibc builds.
* `syspart-app-local.patch` adds an opt-in mode that SysJava does not use, plus
  path lists and script tweaks. SysJava runs its own
  `scripts/compute_syscalls_lowmem.sh` in place of SysPart's
  `compute_syscalls.sh`: the same SysPart invocations, with the call-graph JSON
  and the syscall reachability computed by low-memory equivalents. The JSON is
  byte-identical and the syscall set is the same. `setup.sh` links it in.

The analysis logic is not modified. `PINNED.md` explains why this build, and not
the older Egalito without the jump-table recursion fix, is used.
