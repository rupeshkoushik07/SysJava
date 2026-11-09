# SWAT4J static with the repo's third-party JNI libraries (variant, 2026-11-06)

*Method note from the analysis host. `run_repo_libs_arm.sh` (MODE=replace) is `run_static_jdk8deb.sh` here, the
mapping step is `own_mapping_jdk8deb.sh`; `static_2026-11-09/` and `own_mapping_2026-11-09/` are the runs shipped in
`outputs/`. The other scripts it names (MODE=fill, `compare_arm.py`) are not shipped.*

**Question.** SWAT4J's repo ships six JNI libraries in `JNI_thirdparty/` (Netty epoll, JFFI,
tomcat-native, Sigar 32-bit `libsigar-x86-linux.so`, Hadoop, RocksDB). The original
`binary_analyser.py` reads Netty/JFFI/Sigar from `/home/mrx/Desktop/so/` (the authors' copy of
that folder) and tomcat-native from `/usr/local/apr/lib`. The version we run (facumolina HEAD,
`../../run/`) reads them from each image's own LIBS folder instead, under the same fixed
filenames, so the main table never used `JNI_thirdparty/`. Hadoop and RocksDB have no
mapping step in any SWAT4J version. Does adding the repo libraries change SWAT4J's numbers?

**Command** (SWAT4J code unchanged; only the LIBS folder differs; JARs are the same):
```bash
bash run_repo_libs_arm.sh                                          # MODE=replace: repo copy wins on a name clash (original behaviour)
MODE=fill bash run_repo_libs_arm.sh cassandra_3.0.29 orientdb_3.2.19   # image copy wins; only missing libs added
python3 compare_arm.py > compare_replace.md
python3 compare_arm.py static_fill > compare_fill.md
```
Inputs: datasets as in the main run (`Final_results_JDK8/<T>/Dataset`, cassandra/orientdb from
`../datasets_jar_natives/`). Outputs: `static/`, `static_fill/` (output-native, output-syscalls,
logs), `datasets*/` (LIBS copies, JARFILES symlinks). Native-method lists are identical to the main run.

**Result** (static count; SWAT4J total B = static ∪ dynamic in brackets):

| Image | main (image libs) | + repo libs | change |
|---|---|---|---|
| zookeeper, tomcat, jetty, elasticsearch, groovy, jruby | 104/105/104/105/108/104 | same | none |
| storm | 106 (177) | 116 (178) | +10 Netty epoll: accept4 epoll_create epoll_create1 epoll_ctl epoll_wait eventfd2 getpeername sendmmsg sendmsg splice |
| solr | 103 (173) | 116 (176) | +13: the 10 above + fchdir ftruncate kill |
| orientdb | 105 (169) | replace 103 (168), fill 105 | replace: repo's older JFFI drops fchdir kill |
| cassandra | 116 (179) | 124 (182), same in fill | +14 / −6, not meaningful (O2) |

**Observations.**
- O1. Storm ships Netty epoll as `libnetty_transport_native_epoll_x86_64.so`; SWAT4J only looks for
  `libnetty-transport-native-epoll.so`, so its static analysis misses Netty in the main run. The
  dynamic trace already has most of those syscalls (total B +1). Solr ships no Netty native library,
  so its +13 come from code that cannot load in the container.
- O2. Cassandra's change comes from the repo's 32-bit Sigar: `ldd` resolves it to the host's
  `/lib32/libc.so.6`, so 32-bit libc code enters the analysis and its i386 syscall numbers are named
  with the x86_64 table (mq_getsetattr, ustat, getcpu ...); the 6 lost syscalls are presumably from
  32-bit libc functions shadowing the 64-bit ones of the same name (not verified). Cassandra ships
  `libsigar-amd64-linux.so`, which SWAT4J never looks for (fixed 32-bit filename).
- O3. RocksDB (storm, 942 natives) and Hadoop (solr, 141) natives are unmapped by SWAT4J's static
  analysis in every variant: no mapping step exists for them.
- Conclusion: the main table (image's own libraries) stays; this variant changes SWAT4J's total B by
  at most +3 (solr) and the meaningful change is Storm/Solr Netty.

## Rerun 2026-11-09 (all ten, final Final_results_JDK8 datasets) + SWAT4J mapping with the repo libraries
```bash
SFX=_2026-11-09 JN="" bash run_repo_libs_arm.sh          # MODE=replace, outputs static_2026-11-09/, datasets_2026-11-09/
python3 compare_arm.py static_2026-11-09 > compare_replace_2026-11-09.md
# mapping: count_own_mapping.py per app in the run's mount namespace (work dir static_2026-11-09/work/<t>,
# libs datasets_2026-11-09/<t>/Dataset/LIBS_<t>) -> own_mapping_2026-11-09/<app>.tsv, summary.txt
```
(11-06 outputs kept in static_2026-11-06/, compare_replace_2026-11-06.md.)

| | ZK | Tomcat | Cassandra | Jetty | Storm | OrientDB | ES | Solr | Groovy | JRuby |
|---|---|---|---|---|---|---|---|---|---|---|
| static, image libs (../static_host) | 104 | 105 | 116 | 104 | 106 | 105 | 105 | 103 | 108 | 104 |
| static, + repo libs | 104 | 105 | 124 | 104 | 116 | 105 | 102 | 113 | 108 | 104 |
| mapped, image libs (../own_mapping_2026-11-09) | 129 | 433 | 279 | 124 | 179 | 315 | 174 | 194 | 174 | 330 |
| mapped, + repo libs | 129 | 433 | 408 | 124 | 283 | 351 | 174 | 298 | 174 | 330 |

- O5. Run-to-run variation (correction to the 11-06 orientdb row): with identical inputs SWAT4J's static
  list flips {fchdir, ftruncate, kill} (or {fchdir, kill}) between runs: zookeeper 104/101/104, jruby
  104/102/104, solr 103/106/106 (image libs, 3 runs); orientdb 103 (11-06) vs 105 (11-09) and ES 105 vs 102
  with repo libs. So orientdb's "repo JFFI drops fchdir kill" above and ES's 102 are this variation, not
  the libraries. Same JTracer list and same 12 dependent libraries in the zookeeper 101 and 104 runs;
  PYTHONHASHSEED 0-3 all give 104, so the cause is not Python's hash order (cause not found).
- O6. Mapping with the repo libraries: Storm +104 and Solr +104 (Netty name rule), Cassandra +129 (32-bit
  Sigar's Java_org_hyperic_* names), OrientDB +36 (repo JFFI exports more Java_com_kenai_jffi_* names).
  Hadoop (Solr) and RocksDB (Storm) stay unmapped: no SWAT4J code reads them.

## Decision 2026-11-09 (user): the paper uses this setup
SWAT4J's numbers (static list, mapping) come from static_2026-11-09/ and own_mapping_2026-11-09/ (repo libraries,
MODE=replace, as the original SWAT4J). make_table_jdk8deb.py and package_outputs_jdk8deb.sh read them;
swat4j_vs_sysjava_jdk8.pdf rebuilt. Image-libraries results (../static_host, ../own_mapping_2026-11-09) kept for comparison.

## Check 2026-11-09: every SWAT4J syscall row recomputed from the raw run files
Recomputed from static_2026-11-09/output-syscalls, ../dynamic/<app>_result.txt (clean last try) and SysJava's profile
JSON; all equal make_table_jdk8deb.py, show_results.py and tab:results (Storm "SysJava only" is 33 in tab:results
because it counts the 172-syscall profile without the false-FFM `sync`, 34 elsewhere).
- O7. binary_analyser.py prints N syscall numbers but writes N-3 (N-4 for Cassandra) names. id2name() looks a
  number up as line number+1 of `ausyscall --dump`, which has no lines for 335-423, so every number >= 424 falls
  off the end and is dropped: clone3, faccessat2 (all ten), close_range (Cassandra); plus 0xffffffff (a `mov $-1`).
  SWAT4J behaviour, left unmodified; list in dropped_by_ausyscall_index.txt. (audit userspace 1:3.0.7 on the host.)
- O8. The analysis runs on the host: JDK libraries are the host's OpenJDK 8u504 (Ubuntu build) and `ldd` resolves
  libc/libpthread to the host's glibc 2.35, not the image's glibc 2.28.
- 2026-11-09: Storm's SysJava total A = 172 everywhere (make_table_jdk8deb.py EXCLUDE, package_outputs_jdk8deb.sh,
  show_results.py note): `sync` comes only from false FFM hits, as in tab:results. Storm: A∩B 139, A∖B 33, B∖A 39.
