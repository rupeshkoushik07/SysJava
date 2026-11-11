# Binding-recovery ablation: how to reproduce

SysJava with binding recovery (SysPart starts from the library functions the
application's native methods / FFM downcalls are mapped to) against no binding
(SysPart starts from every function in the library). Same library files, same
SysPart build; only the start functions differ. All commands run from
`~/Tutorial/EchoTrace/ablation`.

Scripts:

| Script | What it does |
|---|---|
| `run_ablation.sh` | SysPart runs per library and arm (header documents every option) |
| `lean_syscalls.py` | syscalls reachable from the start functions, streamed from the `-a 23` call graph |
| `compare.py` | `summary.md`, `per_library_syscalls.tsv` (and `unmapped_loaded.md`) |
| `summary_tex.py`, `summary_pdf.py` | `summary.tex` (paper style) and `summary.pdf` |
| `tomcat_11.0.22/make_bindings.sh` | Tomcat 11 binding start lists and target lists |
| `tomcat_11.0.22/run_jdk_window.sh` | JDK-library runs under the shared-host memory guard |

## Tomcat 11.0.22 (JDK 25, Ubuntu 24.04)

### Inputs (read only)

- Pipeline results: `R=~/Tutorial/EchoTrace_latest/Final_results_latest_versions/tomcat_11.0.22`
  - libraries: `$R/Dataset_symbolized/LIBS_tomcat_11.0.22` (all libraries and dependencies symbolized; no fuzzy functions)
  - mapping: `$R/Bytecode_Analysis/outputs_tomcat_11.0.22` (`mapped_method_syscalls.txt`, `native_methods.txt`, `ffi_hits.txt`, per-library start lists)
  - sysdig trace: `$R/Dynamic_Analysis/sysdig_outputs_tomcat_11.0.22/raw_capture.txt`
  - pipeline binding runs: `$R/Binary_Analysis/syscalls_output_tomcat_11.0.22/<lib>/`
- SysPart: June build, `/home/user/SysPartCode/analysis/app` (the build the pipeline used)
- Container facts: `tomcat_11.0.22/environment.md`

### Steps

1. Binding start lists (`bindings/<lib>.txt`) and target lists (`targets_*.tsv`):

   ```bash
   bash tomcat_11.0.22/make_bindings.sh
   ```

   JNI libraries take the pipeline's own per-library start list. libssl and libcrypto
   take the `downcallHandle` symbols in `ffi_hits.txt` that each library defines
   (75 and 107). The 18 downcall symbols neither library exports are listed in
   `bindings/ffm_not_in_openssl3.txt`. Re-running the script reproduces the
   current files byte for byte (checked 2026-11-05).

2. Both arms for libssl, libcrypto and libtcnative-2. Each arm gets its own call
   graph, rooted at its own start set:

   ```bash
   RESULTS=$R SYMBOLIZED=1 SYSPART_APP=/home/user/SysPartCode/analysis/app LEAN=1 \
     TARGETS=tomcat_11.0.22/targets_small.tsv SKIP="libnet.so libzip.so libjava.so" ARMS="A B" \
     NICE=10 JOB_MEM_GB=12 JOB_TIMEOUT=7200 ./run_ablation.sh tomcat_11.0.22 1
   ```

3. No-binding arm for libnet, libzip and libjava (32 GB cap, 2 h):

   ```bash
   GUARD=kill KILL_BELOW=20 MAX_REQUEUE=2 GATE=50 NICE=10 \
     bash tomcat_11.0.22/run_jdk_window.sh libnet.so:A libzip.so:A libjava.so:A
   ```

   On a machine to yourself, `GUARD=pause GATE=0` skips the memory guard.

4. No-binding arm for libjvm (52,680 start functions):

   ```bash
   GUARD=kill KILL_BELOW=20 MAX_REQUEUE=2 GATE=70 JVM_CAP=60 RSS_STOP_GB=45 NICE=10 \
     bash tomcat_11.0.22/run_jdk_window.sh libjvm.so:A
   ```

   This **did not finish**. SysPart threw `std::bad_alloc` in the `-a 23` call-graph
   step, while generating indirect-call targets, right after "Indirect call target
   resolution":
   - first at a 35 GB address-space cap (19:56–20:34);
   - again at 60 GB (20:36–21:25). That run reached 45 GB resident, was paused
     there, then resumed.

   Logs: `tomcat_11.0.22/A_libjvm.so_try1_35GB.log` and `driver_libjvm_A_try1_35GB.log`
   (35 GB try), `A_libjvm.so.log` and `driver_libjvm_A.log` (60 GB try, with
   `driver_libjvm_A.notes`). There was no third try (host coordinator's decision).
   `A/libjvm.so/DID_NOT_FINISH` holds the reason. `compare.py` then marks the cell
   "not resolved", leaves libjvm out of the totals and prints the reason below the table.

5. Binding arm for libnet, libzip, libjava and libjvm: copied from the pipeline's
   own binding run. Running these as binding-only graphs here was killed twice for
   memory on the shared host; using the pipeline's runs was the user's choice
   (2026-11-05).

   ```bash
   for l in libnet.so libzip.so libjava.so libjvm.so; do
     mkdir -p tomcat_11.0.22/B/$l
     cp $R/Binary_Analysis/syscalls_output_tomcat_11.0.22/$l/{syscalls.txt,startfuncs_with_addr.txt} tomcat_11.0.22/B/$l/
   done
   ```

   `B/<lib>/SOURCE` records this. The pipeline's runs use the same library files,
   SysPart build and start lists.

6. Summary, LaTeX, PDF:

   ```bash
   python3 compare.py tomcat_11.0.22 $R
   python3 summary_tex.py tomcat_11.0.22
   python3 summary_pdf.py tomcat_11.0.22
   ```

### Outputs

`tomcat_11.0.22/summary.md`, `summary.tex`, `summary.pdf`, `per_library_syscalls.tsv`.
Per arm and library: `A|B/<lib>/syscalls.txt`, `startfuncs_with_addr.txt`,
`callgraph_a23.txt.zst` (own runs only).

| Library | Interface | Starts, binding | Syscalls, binding | Starts, no binding | Syscalls, no binding |
|---|---|---:|---:|---:|---:|
| libjava.so | JNI | 69 | 107 (pipeline) | 305 | 115 |
| libjvm.so | JNI | 88 | 104 (pipeline) | 52,680 | not resolved |
| libnet.so | JNI | 5 | 104 (pipeline) | 92 | 109 |
| libtcnative-2.so.0.0.14 | JNI | 92 | 61 | 167 | 62 |
| libzip.so | JNI | 9 | 104 (pipeline) | 205 | 104 |
| libcrypto.so.3 | FFM | 107 | 44 | 10,851 | 68 |
| libssl.so.3 | FFM | 75 | 44 | 1,294 | 60 |
| All except libjvm.so | | 357 | 116 | 12,914 | 127 |

libjvm.so's no-binding syscalls are "not resolved" (step 4), so the last row
leaves it out. With binding it adds no syscall the other six do not already
reach.

Why it is not resolved: SysPart links every indirect call site to every
address-taken function in the code its graph covers.
- With binding, the graph covers 23,969 functions: the `functions` list in the
  pipeline's `libjvm.so/callgraph.json`.
- Without binding, it covers all of libjvm.so: 37,884 indirect call sites
  (`objdump -d` lines matching `call *`) and at least 21,679 address-taken
  functions (`R_X86_64_RELATIVE` relocations whose addend is a function start in
  `nm`).
- That makes about 800 million edges. SysPart ran out of memory at 35 GB and
  again at 60 GB.

What was found:
- **JNI.** SysJava found 269 native methods and mapped 263: 92 libtcnative-2,
  88 libjvm, 69 libjava, 9 libzip, 5 libnet.
- **FFM.** Separately, it found 200 FFM downcalls (tomcat-coyote-ffm.jar → OpenSSL)
  and mapped 182: 107 libcrypto, 75 libssl.
- **JNA and JNR-FFI.** No bindings.

Syscalls reached only without binding: `accept chmod fsync getppid listen mlock
mlock2 rename sendmsg statfs utimensat`.

### Observations and pitfalls

- **The binding arm needs its own call graph.** Reading it off the all-roots graph
  over-counts. This SysPart build resolves every indirect call against the
  address-taken functions in the code the graph reaches, so more roots add
  indirect targets. For libssl that gives 59 syscalls over the all-roots graph
  against 44 from its own graph, which is also the pipeline's 44. See
  `tomcat_11.0.22/validation/RESULT.md`; the invalid values are kept in
  `B_from_all_roots/`.
- **Pipeline and ablation agree on binding.** Where both computed it (libssl,
  libcrypto, libtcnative-2), the binding sets are identical.
- **Pipeline binding files are not sorted.** `B/<lib>/syscalls.txt` copied from the
  pipeline must be sorted before `comm`; `compare.py` uses sets, so it is unaffected.
- **Stripped dependencies inflate results.** They create spurious functions and
  syscalls (Tomcat 7: PLT calls in stripped libuuid treated as address-taken).
  Always use `SYMBOLIZED=1`.

## Tomcat 7.0.109 (JDK 8, Debian 10)

Inputs: `~/Prototype/Final_results_echotrace/tomcat_7.0` (archived pipeline
results). SysPart: July build, the `run_ablation.sh` default
(`../SysPartCode/analysis/app`). Regenerate the outputs:

```bash
python3 compare.py tomcat_7.0
python3 summary_tex.py tomcat_7.0
python3 summary_pdf.py tomcat_7.0
```

These reproduce `summary.md`, `summary.tex`, `per_library_syscalls.tsv` and
`unmapped_loaded.md` byte for byte (checked 2026-11-05).

SysPart runs, as recorded in the session log:

```bash
SKIP="libnet.so" ./run_ablation.sh tomcat_7.0 6
ONLY=libnet.so ./run_ablation.sh tomcat_7.0 2
VARIANTS=M ONLY=libjvm.so ./run_ablation.sh tomcat_7.0 1
VARIANTS=U LOADED=tomcat_7.0/loaded_unmapped.txt ./run_ablation.sh tomcat_7.0 4
```

The libraries with stripped dependencies were then rerun from the symbolized
copies, with the U list limited to the libraries to redo:

```bash
SYMBOLIZED=1 LEAN=1 VARIANTS="A B" SKIP="libj2pkcs11.so libjava.so libjvm.so libmanagement.so libnet.so libzip.so" \
  ./run_ablation.sh tomcat_7.0 4
SYMBOLIZED=1 LEAN=1 VARIANTS=U LOADED=<list> ./run_ablation.sh tomcat_7.0 4
```

The results before symbolization are kept in `tomcat_7.0/stripped_deps/`.

Result: 116 syscalls with binding against 124 without. Found only without binding:
`clock_getres fchdir fsync getppid rt_sigsuspend socketpair times umask`.
Unmapped-library policy: 166.

## All ten JDK 8 images (Debian 10, Temurin 8u504), 2026-11-11

Static analysis only. This uses the same method as Tomcat 7 and 11, applied to every library the final JDK 8 pipeline analysed. Folder: `jdk8_all/`.

### Inputs (read only)
- Pipeline results: `R=~/Tutorial/EchoTrace/Final_results_JDK8/<t>-jdk8-buster`
  - libraries: `$R/Dataset_symbolized/LIBS_<t>`
  - binding runs (start lists and syscalls): `$R/Binary_Analysis/syscalls_output_<t>/<lib>/`
  - final policy: `$R/Binary_Analysis/syscalls_output_<t>/<t>.json`
- SysPart: the same build `run_ablation.sh` uses.

### Steps
1. `python3 jdk8_all/make_targets.py` hashes every analysed library (sha256).
   - Result: 141 library analyses, 38 distinct files, and 37 no-binding runs. Each distinct file is run once, in the first image that has it.
   - libjvm.so is excluded and reported "not resolved" (out of memory at 35 and 60 GB on Tomcat 11).
   - Outputs: `targets/<img>.tsv` and `libraries.tsv`.
2. `bash jdk8_all/run_all.sh` runs arm A (SysPart from every function) for all 8 images that have targets, 2 jobs each, with `LEAN=1`, a 24 GB per-job limit and a 4 h timeout.
   - `jdk8_all/guard.sh` ran alongside: it pauses these runs if MemAvailable drops below 30 GB, so the workload validation keeps priority. It never had to pause anything.
3. Two libraries are stored under a symlink name and first ran with 0 start functions, because SysPart takes the module name from the real file. They were rerun from `targets_fix/` under the real names:
   - `libtcnative-1.so.0.2.28` (Tomcat);
   - `libnetty_transport_native_epoll_x86_64.so` (Storm netty 4.1.30).

   `compare_all.py` uses the reruns (`A_FIX`).
4. `python3 jdk8_all/compare_all.py` writes `summary.md` (one table per image plus an overall table), `per_library.tsv` and `per_image.tsv`.
   - Binding: the pipeline's own run.
   - No binding: the A run, matched by sha256.
   - Two names for one file count as one library.
   - Profile without binding: the final policy plus every library's no-binding set; libjvm keeps its binding set.

### Observations
- Every library passes the check: no binding run reaches a syscall that its no-binding run misses.
- The largest effect is libc-2.28 in Cassandra and Elasticsearch, which JNA binds to directly.
  - With binding, the pipeline maps 3 libc functions in Cassandra (3 syscalls) and 5 in Elasticsearch (37 syscalls).
  - Without binding, every one of the 3,125 libc exports is a start, and 273 syscalls are reached.
  - This is what drives the +74 (Cassandra) and +112 (Elasticsearch) profile increases.
