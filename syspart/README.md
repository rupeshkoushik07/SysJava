# SysPart

SysJava uses SysPart for the binary call-graph analysis. SysPart is a
third-party tool built on the Egalito binary recompiler. Every result in this
artifact uses one pinned build:

| | |
|---|---|
| SysPartCode | https://github.com/vidyalakshmir/SysPartCode @ `453694d9e16e6348cd8b1471321ee538fa02c416` (unmodified) |
| Egalito | https://github.com/stevens-s3lab/egalito @ `8f94390ea06ee90c499705013a42bec41abb4b7b` (v1.0.0-93) + `egalito-local.patch` |
| `syspart` md5 | `3618898bddb178963302e573fee69c97` |

## Build

Tested on Ubuntu 22.04. Prerequisites as in SysPartCode's README
(`make g++ libreadline-dev gdb lsb-release unzip libc6-dbg`).

```bash
ART=/path/to/artifact
git clone https://github.com/vidyalakshmir/SysPartCode.git && cd SysPartCode
git checkout 453694d9e16e6348cd8b1471321ee538fa02c416
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

SysJava calls the `syspart` binary through its own
`scripts/compute_syscalls_lowmem.sh` instead of SysPart's `compute_syscalls.sh`.
It makes the same SysPart invocations and computes the call-graph JSON and the
syscall reachability with lower memory use. The JSON is byte-identical and the
syscall set is the same. `setup.sh` links it in.

## Why Egalito 8f94390e

The Egalito commit SysPartCode points at (`2b61af0d`, v1.0.0-90) recurses
without bound on the JDK 13/17 `libjvm.so` of elasticsearch_7.5.2, groovy_4.0.0
and jetty_9.4.51. `8f94390e` has the fix. Where both work, they give identical
`allfunctions.txt` and `syscalls.txt`.

`egalito-local.patch` makes Egalito skip an unresolved lazy PLT entry instead of
dereferencing a null pointer, a crash seen on stripped glibc builds. It does not
change the analysis of anything Egalito could already load.
