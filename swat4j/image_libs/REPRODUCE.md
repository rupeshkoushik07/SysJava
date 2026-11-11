# SWAT4J's static step on the IMAGE's libraries (2026-11-11)

*Method note from the analysis host. In the artifact the run is `run_image_libs.sh` here, after
`../run_static_jdk8deb.sh` (its native-method lists and datasets: `../jdk8_debian10/static/`); its static allowlists and
logs are shipped in `../outputs/static/`. `compare_full.py` is `../show_results.py` here.*

**Question.** The paper's SWAT4J run (`../repo_libs_arm/static_2026-11-09`) ran `binary_analyser.py` on the host. So:
- JDK libraries were the host's Ubuntu OpenJDK 8u504 (hard-coded `/usr/lib/jvm/java-8-openjdk-amd64/jre/lib/amd64`);
- every dependency was resolved by the host's `ldd`: glibc 2.35, plus "not found" for libraries the host lacks, e.g. tcnative's libapr.

SysJava analyses each image's own files (glibc 2.28, Temurin 8u504). What do SWAT4J's numbers look like on the image's files?

**SWAT4J code unchanged.** Only its environment changes, in `run_image_libs.sh`:
1. **JDK.** Inside the per-app mount namespace, the image's `jre/lib/amd64` is bind-mounted over the hard-coded path.
   - The copy is `rootfs/<T>/jdk_dynsym`: `.symtab` is removed with `strip --strip-all`.
   - SWAT4J's parser needs labels like `<Java_...@@SUNWprivate_1.1>`, which is what Ubuntu's stripped JDK gives. Temurin keeps `.symtab`, so the parser crashes on it.
   - `.text` bytes are identical (checked: libjava, libjvm, libnio).
2. **Dependencies.** `bin/ldd` comes first in PATH and does what `ldd` does (`LD_TRACE_LOADED_OBJECTS=1` on the loader), but:
   - with the image's own `ld-2.28.so`, `--inhibit-cache`;
   - searching the image's `LD_LIBRARY_PATH` and `/etc/ld.so.conf.d` directories, inside `rootfs/<T>`;
   - reporting a library the image lacks as "not found". Otherwise the loader's built-in fallback picks the host's copy (this happened with Groovy's X11 libraries).
   - Every lookup is logged in `static/logs/<T>.ldd`. After the fix, no library resolves outside the image.
3. **Native-method lists.** The paper run's `output-native` files are reused, so only the libraries differ. Same datasets as the paper run (repo `JNI_thirdparty` libraries, MODE=replace).

```bash
./extract_rootfs.sh                   # rootfs/<T>: /lib, /lib64, /usr/lib/x86_64-linux-gnu, ld.so.conf, jre/lib/amd64, LD_LIBRARY_PATH dirs; jdk_dynsym
./run_image_libs.sh                   # static/output-syscalls (about 5-7 min, 10 in parallel)
OUT=$PWD/static_run2 ./run_image_libs.sh   # second run, for run-to-run noise
```

**Results.**
- `compare_host_vs_image.md`: static lists.
- `compare_full.md`: SWAT4J's total B = static ∪ dynamic, against SysJava, as in tab:results.

| | ZK | Tomcat | Cassandra | Jetty | Storm | OrientDB | ES | Solr | Groovy | JRuby |
|---|---|---|---|---|---|---|---|---|---|---|
| static, host libs (paper) | 104 | 105 | 124 | 104 | 116 | 105 | 102 | 113 | 108 | 104 |
| static, image libs (run 1 / 2) | 108/108 | 123/122 | 119/119 | 108/108 | 118/118 | 109/109 | 109/109 | 118/118 | 108/105 | 105/107 |
| total B, host libs (paper) | 171 | 170 | 182 | 171 | 178 | 169 | 174 | 175 | 175 | 170 |
| total B, image libs | 170 | 176 | 179 | 170 | 177 | 168 | 173 | 175 | 171 | 168 |

**Observations.**
- **The static lists change a lot in content, though not in size.** Each image gains about 20 syscalls and loses about 18, the same in both image runs.
  - Gained with glibc 2.28: stat, lstat, fstat, time, gettimeofday, nanosleep, pipe, pause, setitimer, setresuid/gid, ...
  - Lost (glibc 2.35 only): newer wrappers such as faccessat, getrandom, set_robust_list, clock_nanosleep, timerfd_*, unlinkat, symlink/link, sendfile, ...
  - Some gained names (adjtimex, ustat, migrate_pages, rt_sigqueueinfo) come from SWAT4J's register-based syscall-number guess. They are kept as SWAT4J reports them.
- **Run-to-run noise between the two image runs:** 0-4 syscalls (ftruncate, mkdir, migrate_pages, brk).
- **SWAT4J's total B changes by -4 to +6 per image,** because the dynamic trace already holds most of the swapped syscalls. Overlap with SysJava rises by 1 to 8; SWAT4J-only syscalls fall by 2 to 6.
- **Tomcat:** the image has libapr (found), which the host lacked. The repo tcnative's OpenSSL 1.0.0 is missing in both.
- **Cassandra:** the repo's 32-bit Sigar fails `ldd` with "wrong ELF class" on the image's 64-bit loader. The image has no 32-bit libc, so no /lib32 code enters, unlike the host run.
- **Host JDK version:** it was upgraded to 8u512 on 2026-11-10, so the paper's host run cannot be repeated exactly any more.

**Table V with SysJava's fixed profiles (2026-11-11).** `python3 compare_full.py` -> `compare_full_fixes.md` (A after the
three analysis fixes, Final_results_JDK8 + `_tables/storm_no_false_ffm_fixes`); `python3 compare_full.py --before` reproduces
`compare_full.md` (A before the fixes) exactly. B is unchanged.
