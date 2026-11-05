# SWAT4J baseline

SWAT4J (https://github.com/facumolina/SWAT4J, commit `6929d66`) is the tool
SysJava is compared against in Table `tab:results`. It is run **unmodified**. Its
bugs, crashes and coverage gaps are reported as they are. Only the environment
it expects is provided.

| File | Purpose |
|---|---|
| `setup_swat4j.sh` | Clone SWAT4J at the pinned commit into `run/`, compile its bytecode tracer with JDK 8 |
| `run_swat4j_host.sh <image>...` | SWAT4J static analysis on the host's OpenJDK 8. Uses the JARs/libraries of a SysJava result (`DATASETS=<results dir>`) |
| `run_swat4j.sh` | The same in an Ubuntu 18.04 container (`docker/Dockerfile`). Earlier variant, kept for reference |
| `dynamic_swat4j.sh <app>...` | SWAT4J dynamic analysis as in its paper: `strace -f -c` on containerd while the image starts |
| `swat4j_mapping.py` | SWAT4J's JNI-name mapping (from `binary_analyser.py`) as a standalone script. Used by `analysis/coverage.sh` |
| `compare_allowlists.py`, `make_paper_table.py` | SysJava vs SWAT4J allowlist comparison and table |
| `mrx_desktop/native` | OpenJDK 8 native sources that SWAT4J reads from `/home/mrx/Desktop/native` |
| `outputs/`, `RESULTS.md` | Allowlists produced for the paper and notes on the reruns (added with the results) |

Environment-only adaptations, none of which change SWAT4J's code:

* SWAT4J hard-codes `/home/mrx/Desktop` and `/usr/local/apr/lib`. Each application
  runs in its own mount namespace with these paths bind-mounted, because SWAT4J
  rewrites `soname/` on every run.
* `--jdk-lib` of the mapper points at the container's own JDK libraries, since
  the host JDK it defaults to may not be installed.
* `ausyscall` calls syscalls 17/18 `pread`/`pwrite`, while Docker profiles call
  them `pread64`/`pwrite64`. The comparison scripts alias the two names.
