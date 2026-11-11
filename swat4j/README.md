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
| SysJava total (A) | 192 173 230 161 179 174 185 201 189 168 |
| SWAT4J static ∪ dynamic (B) | 170 176 179 170 177 168 173 175 171 168 |
| SWAT4J static | 108 123 119 108 118 109 109 118 108 105 |
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
| `image_libs/extract_rootfs.sh` | copy from each image the files SWAT4J's binary step reads: the loader, the system library folders, `/etc/ld.so.conf*`, the JDK's native libraries and the `LD_LIBRARY_PATH` folders (`image_libs/rootfs/<image>/`); needs the images (`../docker_images/build_jdk8_images.sh`) |
| `image_libs/run_image_libs.sh [image...]` | SWAT4J's binary step again, on each image's own libraries: the image's JDK is bind-mounted over the path SWAT4J hard-codes, and `image_libs/bin/ldd` resolves dependencies with the image's loader and folders (a library the image lacks is "not found"). Same native-method lists and datasets as `run_static_jdk8deb.sh`. Output in `jdk8_debian10/image_libs/`: the static allowlists of the table |
| `dynamic_all_jdk8deb.sh [app...]` | dynamic analysis: `strace -f -c` on containerd while each image starts (`dynamic_swat4j_jdk8deb.sh`); a run during which another container started is repeated. Output in `jdk8_debian10/dynamic/` |
| `package_outputs_jdk8deb.sh <dir>` | collect the runs (native methods and mapping from the first two, static allowlists from the image-library run, dynamic) and SysJava's allowlists (`ET=` as above, default the shipped results) into one folder for `show_results.py` |

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

**Image libraries.** SWAT4J's binary step hard-codes the JDK path and uses
`ldd`, so on the analysis host it read the host's JDK and resolved every
dependency against the host's glibc. The table uses the run on each image's own
JDK and libraries, the files SysJava analyses (`image_libs/REPRODUCE.md`: the
static list changes by about 20 syscalls each way; B by -4 to +6).

**What a rerun may change.**
- SWAT4J's static list varies between identical runs: by 0 to 4 syscalls on the
  image libraries (`ftruncate`, `mkdir`, `migrate_pages`, `brk`; Groovy 108 and 105,
  JRuby 105 and 107 on two runs), and by `fchdir`, `ftruncate` and `kill` on the
  host libraries. The cause was not found; `PYTHONHASHSEED` 0-3 gives the same
  result, so it is not Python's hash order.
- On the host libraries, Cassandra's static count included code from the 32-bit
  Sigar's 32-bit libc. The images have no 32-bit libc, so on the image libraries
  the 32-bit Sigar fails `ldd` and adds nothing.

`REPRODUCE_repo_libs.md` is the method note of the repository-library runs, with
the counts with and without the repository libraries; `image_libs/REPRODUCE.md`
compares the host and image libraries.

**tab:results.** Its SWAT4J rows (`../2_swat4j_vs_sysjava/tables/`,
`../tools/make_tab_results_jdk8.py`) come from the same outputs: SWAT4J Java Lib
from `outputs/static/syscalls/` (image libraries), SWAT4J Natives Found and the mapping rows from
`outputs/mapping/<app>.tsv` (Resolved + Not Found = Natives Found), Dynamic from
`outputs/dynamic/`.
