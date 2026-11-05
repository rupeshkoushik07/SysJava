# Pinned SysPart build

All EchoTrace binary analysis (and the Confine comparison) uses **one** SysPart
build, so results do not depend on which checkout a person happens to run.

| | Value |
|---|---|
| Location | `/home/user/SysPartCode/analysis/app` (`build_x86_64/syspart`) |
| SysPartCode | `https://github.com/vidyalakshmir/SysPartCode.git` @ `453694d9e16e6348cd8b1471321ee538fa02c416` + `syspart-app-local.patch` |
| Egalito | `https://github.com/stevens-s3lab/egalito.git` @ `8f94390ea06ee90c499705013a42bec41abb4b7b` (v1.0.0-93) + `egalito-local.patch` |
| `syspart` md5 | `3618898bddb178963302e573fee69c97` |
| `libegalito.so` md5 | `9db223d18222a931596c428558dc5389` |
| Built | 2026-06-24 |

## Local patches

- `egalito-local.patch`: skip an unresolved lazy PLT entry and unresolved
  libraries instead of dereferencing a null symbol list / empty path (the
  stripped-libc crash in artifacts/cassandra_5.0.6-bookworm/diagnosis.txt).
- `syspart-app-local.patch`: an opt-in `SYSPART_ROOT_ONLY=1` mode (not used by
  EchoTrace; unset = upstream behaviour), dlanalysis path lists, and script
  tweaks. EchoTrace runs its own `scripts/compute_syscalls_lowmem.sh`, so the
  patched `compute_syscalls.sh`/`getsyscalls.py` in that tree are not used.

## Why this build and not `EchoTrace/SysPartCode`

`EchoTrace/SysPartCode` (built 2026-07-27) is the same SysPartCode commit but
points at the **older** Egalito `2b61af0d` (v1.0.0-90) without the patches. It
recurses without bound (stack overflow, also with an 8 GB stack) on the JDK
13/17 `libjvm.so` of elasticsearch_7.5.2, groovy_4.0.0 and jetty_9.4.51, even
on the original unmodified dataset files.

Where the July build works, both builds give identical output. Checked on
2026-11-05 (same inputs, same start functions, sorted `allfunctions.txt` and
`syscalls.txt` compared):

| ELF | functions | syscalls | identical |
|---|---|---|---|
| storm_2.4.0 `bash` | 5,651 | 81 | yes |
| solr_8.7.0 `find` | 5,589 | 69 | yes |
| cassandra_3.0.29 `libjava.so` | 35,692 | 87 | yes |
| orientdb_3.2.19 `libnet.so` | 35,869 | 82 | yes |

So results already produced with the July build stay valid; new runs use this
pin. `scripts/rerun_syspart_symbolized.sh` defaults to it (override with
`SYSPART_APP=`), and each result directory records the build that made it in
`syspart_build.txt`.

## Checking a machine

```bash
md5sum /home/user/SysPartCode/analysis/app/build_x86_64/syspart
# expect 3618898bddb178963302e573fee69c97
```

## Rebuilding elsewhere

```bash
git clone https://github.com/vidyalakshmir/SysPartCode.git && cd SysPartCode
git checkout 453694d9e16e6348cd8b1471321ee538fa02c416
git submodule update --init --recursive
git -C analysis/tools/egalito checkout 8f94390ea06ee90c499705013a42bec41abb4b7b
git -C analysis/tools/egalito apply /path/to/EchoTrace/syspart-pin/egalito-local.patch
git apply /path/to/EchoTrace/syspart-pin/syspart-app-local.patch
./build_upgraded_egalito.sh
```

A rebuilt binary will not have the same md5 (compiler and paths differ);
re-run the four checks above against it instead.
