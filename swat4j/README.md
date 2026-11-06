# SWAT4J baseline

SWAT4J (https://github.com/facumolina/SWAT4J, commit `6929d66`) is run
**unmodified** on the ten JDK 8 images of Table `tab:results`: no fixes and no
workarounds. Only the environment it expects is provided.

## Shipped outputs

`outputs/` holds SWAT4J's static and dynamic allowlists for the ten images,
its native-method mapping, and SysJava's allowlists for the same images
(`outputs/README.md` lists every file). To print the table:

```bash
python3 show_results.py outputs           # the table
python3 show_results.py outputs --sets    # also the syscalls only SysJava / only SWAT4J allows
```

## Rerun

`../2_swat4j_vs_sysjava/reproduce.sh` runs these in order:

| Script | Step |
|---|---|
| `setup_swat4j.sh` | clone SWAT4J at the pinned commit into `run/`, compile it with JDK 8 (once) |
| `run_swat4j_host_out.sh <image>...` | static analysis on the JARs and libraries SysJava captured (`DATASETS=<results>`) |
| `dynamic_all_jdk8deb.sh [app...]` | dynamic analysis: `strace -f -c` on containerd while each image starts (`dynamic_swat4j_jdk8deb.sh`); a run during which another container started is repeated. Needs sudo |
| `package_outputs_jdk8deb.sh <dir>` | collect the outputs into one folder for `show_results.py` |

SWAT4J hard-codes `/home/mrx/Desktop` and `/usr/local/apr/lib`; each image runs
in its own mount namespace with these paths bind-mounted (`mrx_desktop/` holds
the OpenJDK 8 sources it reads there). `ausyscall` names syscalls 17/18
`pread`/`pwrite` where Docker uses `pread64`/`pwrite64`; the two are aliased.
