# SWAT4J baseline

SWAT4J (https://github.com/facumolina/SWAT4J, commit `6929d66`) is run
**unmodified** on the ten JDK 8 images of Table `tab:results`: no fixes and no
workarounds. Only the environment it expects is provided. SWAT4J finds its own
native methods (its bytecode analysis, JTracer) and maps those with its own
rules; SysJava's list of native methods is never given to it.

## Shipped outputs

`outputs/` holds SWAT4J's static and dynamic allowlists for the ten images,
the native methods it found and how it mapped them, and SysJava's allowlists
for the same images (`outputs/README.md` lists every file). To print the table:

```bash
python3 show_results.py outputs           # the table
python3 show_results.py outputs --sets    # also the syscalls only SysJava / only SWAT4J allows
```

Expected (ZooKeeper, Tomcat, Cassandra, Jetty, Storm, OrientDB, Elasticsearch, Solr, Groovy, JRuby):

| Row | Values |
|---|---|
| SysJava total (A) | 190 170 230 157 173 173 183 199 189 167 |
| SWAT4J static ∪ dynamic (B) | 171 170 182 171 178 169 174 175 175 170 |
| SWAT4J static | 104 105 124 104 116 105 102 113 108 104 |
| SWAT4J dynamic | 128 127 141 128 137 129 137 136 130 128 |
| native methods SWAT4J finds | 236 614 686 225 1529 519 368 613 334 448 |
| mapped by SWAT4J | 129 433 408 124 283 351 174 298 174 330 |

## Rerun

`../2_swat4j_vs_sysjava/reproduce.sh` runs these in order (`SKIP_SYSJAVA=1` for
SWAT4J alone, on the shipped capture):

| Script | Step |
|---|---|
| `setup_swat4j.sh` | clone SWAT4J at the pinned commit into `run/`, compile it with JDK 8 (once) |
| `run_static_jdk8deb.sh [image...]` | static analysis. Each image's JARs and native libraries as SysJava captured them (`ET=<SysJava results>`, default: unpacked from the shipped capture in `../2_swat4j_vs_sysjava/sysjava_results/<image>/dataset/`), plus SWAT4J's own `run/JNI_thirdparty/` libraries, the repository copy winning on a name clash. Runs `run_swat4j_host_out.sh`. Output in `jdk8_debian10/static/` |
| `own_mapping_jdk8deb.sh [image...]` | SWAT4J's mapping of the native methods it found, counted per method (`count_own_mapping.py`, in the static run's mount namespace). Output in `jdk8_debian10/own_mapping/<app>.tsv` |
| `dynamic_all_jdk8deb.sh [app...]` | dynamic analysis: `strace -f -c` on containerd while each image starts (`dynamic_swat4j_jdk8deb.sh`); a run during which another container started is repeated. Output in `jdk8_debian10/dynamic/` |
| `package_outputs_jdk8deb.sh <dir>` | collect the three runs and SysJava's allowlists (`ET=` as above, default the shipped results) into one folder for `show_results.py` |

All but `setup_swat4j.sh` need sudo. SWAT4J hard-codes `/home/mrx/Desktop` and
`/usr/local/apr/lib`; each image runs in its own mount namespace with these
paths bind-mounted (`mrx_desktop/` holds the OpenJDK 8 sources it reads there).
`ausyscall` names syscalls 17/18 `pread`/`pwrite` where Docker uses
`pread64`/`pwrite64`; the two are aliased.

**Repository libraries.** SWAT4J's repository ships six JNI libraries in
`JNI_thirdparty/`. The original SWAT4J read them from the authors' folder
`/home/mrx/Desktop/so`; the version we run reads them from the image's library
folder under fixed names, so `run_static_jdk8deb.sh` copies them there. Four are
read: Netty epoll, JFFI, the 32-bit Sigar, and tomcat-native (through
`/usr/local/apr/lib`, which `run_swat4j_host_out.sh` fills from the library
folder). Hadoop and RocksDB are never read.

**What a rerun may change.**
- SWAT4J's static list varies between identical runs by `fchdir`, `ftruncate`
  and `kill` (ZooKeeper gave 104, 101, 104 on three runs). The cause was not
  found; `PYTHONHASHSEED` 0-3 gives the same result, so it is not Python's hash
  order. A rerun may differ by up to 3 in the static count and 1 in B.
- Cassandra's static count includes code from the 32-bit Sigar's 32-bit libc,
  whose i386 syscall numbers SWAT4J names with the x86-64 table.

`REPRODUCE_repo_libs.md` is the method note of these runs, with the counts
with and without the repository libraries.

**tab:results.** Its SWAT4J rows (`../2_swat4j_vs_sysjava/tables/`,
`../tools/make_tab_results_jdk8.py`) come from the same outputs: SWAT4J Java Lib
from `outputs/static/syscalls/`, SWAT4J Natives Found and the mapping rows from
`outputs/mapping/<app>.tsv` (Resolved + Not Found = Natives Found), Dynamic from
`outputs/dynamic/`.
