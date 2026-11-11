# Binding vs no binding: all ten JDK 8 images

SysPart is run on each library two ways. With **binding**, it starts from the library functions the application's native methods map to; these are the pipeline's own runs in `2_swat4j_vs_sysjava/sysjava_results`. With **no binding**, it starts from every function in the library. Both use the same library file and the same SysPart build. Only the static analysis is compared.

Every image runs on JDK 8u504 (Eclipse Temurin) on Debian 10.

| Application | Profile with binding | Profile without binding | Added |
|---|---:|---:|---:|
| Apache ZooKeeper 3.4.14 | 192 | 201 | +9 |
| Apache Tomcat 7.0.109 | 173 | 180 | +7 |
| Apache Cassandra 3.0.29 | 230 | 304 | +74 |
| Eclipse Jetty 9.4.51 | 161 | 173 | +12 |
| Apache Storm 2.4.0 | 179 | 187 | +8 |
| OrientDB 3.2.19 | 174 | 183 | +9 |
| Elasticsearch 7.5.2 | 185 | 295 | +110 |
| Apache Solr 8.7.0 | 201 | 205 | +4 |
| Apache Groovy 4.0.0 | 189 | 198 | +9 |
| JRuby 9.4.2.0 | 168 | 177 | +9 |
| **Mean** | **185.2** | **210.3** | **+25.1** |

- **Profile with binding** is the published profile (2026-11-11, after the three analysis fixes: libjvm's imported libraries, vtable start functions for C++ libraries, `fchown` in the runc whitelist; Storm without the false-FFM `sync`).
- **Profile without binding** is the published profile plus every library's no-binding syscalls. libjvm.so keeps its binding set.
- The fixes change only the binding side: libfontmanager and libsunec start from more functions (no new syscalls), and Storm's RocksDB reaches 70 syscalls instead of 59. The no-binding runs are unchanged.
- **libjvm.so has no no-binding result** ("not resolved"). It ran out of memory (`std::bad_alloc`) at 35 GB and again at 60 GB on Tomcat 11.
- **Cassandra and Elasticsearch gain the most** because of libc-2.28, which JNA calls directly.
  - With binding, SysPart starts from the 3 (Cassandra) or 5 (Elasticsearch) mapped libc functions.
  - Without binding, it starts from all 3,125 libc functions and reaches 273 syscalls.
- **No library reaches a syscall with binding that it misses without binding.**
- **Per-library tables:** `results/summary.md`, `results/per_library.tsv`, `results/per_image.tsv`.

## Reproduce

All commands run from `analysis/binding_ablation/jdk8_all`.

**1. Tables from the shipped results** (seconds, no SysPart needed):

```bash
python3 unpack_libs.py          # work/<image>/Dataset_symbolized/LIBS_<image> (about 650 MB)
python3 make_targets.py         # targets/<image>.tsv, results/libraries.tsv
python3 compare_all.py          # results/summary.md, per_library.tsv, per_image.tsv
```

**2. Rerun the 37 no-binding SysPart runs** (several hours; peak about 24 GB per run). This needs a SysPart build (`syspart/README.md`):

```bash
SYSPART_APP=/path/to/SysPartCode/analysis/app JOBS=2 bash run_all.sh   # replaces results/A/
python3 compare_all.py
```

### What the steps do
- **Inputs:** `inputs/libs.tar.xz` holds the symbolized libraries of the ten images, each distinct file stored once by its sha256. `inputs/manifest.tsv` places those files back into each image's folder.
- **Runs:** `make_targets.py` gives each distinct library file one no-binding run: 141 library analyses, 38 distinct files, 37 runs.
- **Rerun script:** `run_all.sh` calls `../run_ablation.sh` with arm A, `LEAN=1`, `SYMBOLIZED=1`, and a 24 GB / 4 h limit per run.
