# Experimental environment (recorded 2026-11-06)

Everything the Table II (`tab:results`, JDK 8) and Table III (`tab:latest`) results were produced with.
Image digests are in `images.tsv`, the images themselves in `tarballs/` (see `README.md`).

## Host

| Item | Value |
|---|---|
| Machine | KVM guest, "QEMU Virtual CPU version 2.5+", x86_64, 24 vCPUs (24 sockets x 1 thread) |
| Memory / swap | 125 GB RAM; 127 GB swap (/dev/vdc 64 GB SSD prio 100, /dev/vdb 64 GB prio 10) |
| OS | Ubuntu 22.04.5 LTS |
| Kernel | Linux 5.15.0-202-generic #212-Ubuntu SMP (x86_64) |
| Kernel seccomp actions | kill_process kill_thread trap errno user_notif trace log allow |
| Note | The VM had 8 vCPUs until 2026-11-05 ~11:50 (admin upgrade to 24 vCPUs + 2nd swap disk); results finished before that ran on 8 vCPUs. Timing is not part of any result. |

## Container runtime

| Component | Version |
|---|---|
| Docker (docker.io) | 29.1.3 (client and server, API 1.52), package 29.1.3-0ubuntu3~22.04.2 |
| containerd | 2.2.1 (package 2.2.1-0ubuntu1~22.04.2) |
| runc | 1.3.4-0ubuntu1~22.04.1 (spec 1.2.1, go1.24.4); runc-dbgsym installed (used for the runc whitelist work) |
| Docker config | storage overlay2, cgroup driver systemd, cgroup v2, default runtime runc, security options apparmor + seccomp (builtin) + cgroupns |
| libseccomp | libseccomp2 2.5.3-2ubuntu3~22.04.1 (host; Docker applies the generated JSON profiles through it) |
| sysdig (capture) | 0.41.4, `--modern-bpf` |
| auditd (seccomp LOG checks) | 1:3.0.7-1ubuntu0.1 |

## Analysis tools

| Tool | Version / build |
|---|---|
| SysPart | one binary for every run: `analysis/app/syspart` sha256 `91121663a9b17b3f...`, commit 453694d (2026-06 build; EchoTrace_latest/SysPartCode, EchoTrace/SysPartLowmem and ~/SysPartCode all hold it). The July build (sha256 `b5bd7962...`, EchoTrace/SysPartCode) was NOT used (infinite recursion on JDK 13/17 libjvm). |
| EchoTrace (JDK 8 pipeline) | repo ~/Tutorial/EchoTrace at 4823b44 + uncommitted script fixes made 2026-11-05/06 (list in the session notes) |
| EchoTrace (latest pipeline) | repo ~/Tutorial/EchoTrace_latest at 516fb46 + uncommitted script fixes |
| Bytecode analysis (stage 4) | PrototypeFinal/JNADetector with the <clinit> + inherited-method fix, commit 52628c4 (branch latest-clinit-fix, ~/Tutorial/EchoTrace_clinit_build); patch sha256 332e88ea... |
| SootUp / ASM | SootUp (org.soot-oss sootup.*) and ASM 9.9 from ~/.m2 |
| SWAT4J | upstream https://github.com/facumolina/SWAT4J commit 6929d66, unmodified (~/SWAT4J) |
| Host JDK (analysis tools) | OpenJDK 17.0.20.1 (Ubuntu build) |
| Others | Python 3.10.12, gcc 11.4.0, Maven 3.6.3, Go 1.26.8 (runc source analysis: go1.24.4 toolchain, x/tools v0.30.0) |

## JDK builds and C library inside the images

| Image | JDK | OS | glibc |
|---|---|---|---|
| cassandra:5.0.8 | Temurin 17.0.19+10 | Debian 12 | 2.36 |
| zookeeper:3.9.5 | Temurin 17.0.19+10 | Ubuntu 22.04.5 | 2.35 |
| tomcat:11.0.22 | Temurin 25.0.3+9-LTS | Ubuntu 24.04.4 | 2.39 |
| solr:10.0.0 | Temurin 25.0.3+9-LTS | Ubuntu 24.04.4 | 2.39 |
| groovy:5.0.6 | Temurin 21.0.11+10-LTS | Ubuntu 24.04.4 | 2.39 |
| orientdb:3.2.53 | Temurin 1.8.0_492-b09 | Ubuntu 26.04 | 2.43 |
| jetty:12.1.10 | Temurin 25.0.3+9-LTS | Ubuntu 26.04 | 2.43 |
| elasticsearch:7.1.0 | bundled OpenJDK 12.0.1+12 | CentOS 7 | 2.17 |
| storm:2.8.8 | Temurin 17.0.19+10 | Ubuntu 26.04 | 2.43 |
| jruby:10.1.0.0 | Temurin 21.0.11+10-LTS | Ubuntu 24.04.4 | 2.39 |
| all 10 `*-jdk8-buster` | Temurin 1.8.0_504-b01 | Debian 10 | 2.28 |
| zookeeper:3.7 (storm 2.4.0 sidecar) | Temurin 11.0.25+9 | Ubuntu 22.04.5 | 2.35 |

## Launch commands

Per-target arguments come from `EchoTrace_latest/scripts/run_latest_target.sh` and
`EchoTrace/scripts/run_jdk8_target.sh` (and the same values in the SWAT4J dynamic script).

| Target | docker run arguments | Command | Readiness marker |
|---|---|---|---|
| cassandra (5.0.8, 3.0.29) | `-e MAX_HEAP_SIZE=1G -e HEAP_NEWSIZE=256M` | default | `Startup complete` (5.0.8) / `Starting listening for CQL clients` (3.0.29) |
| zookeeper (3.9.5, 3.4.14) | none | default | `binding to port` |
| tomcat (11.0.22, 7.0) | none | default | `Server startup in` |
| solr | none | default | `o.e.j.s.Server Started` (10.0.0) / `Started @` (8.7.0) |
| groovy | `-it` (5.0.6) | default | `Groovy Shell` (5.0.6) / `Groovy 4.0.0 on` (4.0.0) |
| orientdb | `-e ORIENTDB_ROOT_PASSWORD=root` | default | `Listening http connections` (3.2.53) / `OrientDB Studio available` (3.2.19) |
| jetty | none | default | `oejs.Server:main: Started` (12.1.10) / `Started @` (9.4.51) |
| elasticsearch | 7.1.0: `-e discovery.type=single-node -e ES_JAVA_OPTS="-Xms1g -Xmx1g"`; 7.5.2: `-e ES_JAVA_OPTS="-Xms1g -Xmx1g"` | default | `"message": "started"` / ` started` |
| storm | `--network et-latest-net` / `et-jdk8-net --hostname nimbus --network-alias nimbus`, ZooKeeper sidecar (zookeeper:3.9.5 / zookeeper:3.7) on that network | `storm nimbus` / `nimbus` | `Starting nimbus server` in /logs/nimbus.log (2.8.8); JVM up (2.4.0) |
| jruby | `-it` | default (irb) | none: JVM up for 30 s |

- **Capture (stage 2)**: `sysdig --modern-bpf --cpus-for-each-buffer 1 --unbuffered`, filters
  `container.name=<c> and evt.type in (open,openat,openat2,mmap)` (.so/.jar) and `evt.type=execve`, for
  120 s. The container created in stage 1 is stopped and started again (`docker stop`/`docker start`), so
  the capture records a restart; first-start-only code is missed (solr `cp`, storm `cat`; added by hand).
- **Run under the profile (stage 10/11, `verify_seccomp_profile.sh`)**: one baseline run without the
  profile and one run with `--security-opt seccomp=<profile>.json`, same arguments; each stays 60 s
  (`STAY=60`, readiness timeout 240 s); checks: readiness marker, still running, HTTP/TCP probe
  (ES 9200, solr/tomcat/jetty/orientdb HTTP, cassandra/zookeeper TCP), new EPERM lines vs baseline.
- **SWAT4J dynamic** (`~/Tutorial/swat4j/dynamic_swat4j_jdk8deb.sh`): `strace -f -c` attached to Docker's
  containerd, container started with the arguments above, stopped at the readiness marker (max 180 s).
- **Native recall (benchmark 1)** (`EchoTrace/scripts/native_recall_capture.sh`): same arguments plus
  `-e JAVA_TOOL_OPTIONS=-verbose:jni` (ES: in ES_JAVA_OPTS).
- **Seccomp LOG checks** (runc whitelist, ES ML diagnosis): profile with `defaultAction` SCMP_ACT_LOG,
  records read from /var/log/audit/audit.log via `ausearch -m SECCOMP`.

## Repetitions

| Step | Repetitions |
|---|---|
| Capture (stage 2) | 1 per image (120 s) |
| Static analysis (stages 4-9) | deterministic, 1 run; SysPart crash exclusion tries each start function once (900 s limit) |
| Run under the profile (stage 10/11) | 1 baseline + 1 profiled run per image (60 s each); repeated only after an analysis fix (each before/after kept, e.g. `*_before_main`, `*_before_uumain`, `*_before_cp`) |
| SWAT4J static | 1 run per image (deterministic) |
| SWAT4J dynamic | 1 accepted run per image; a run is rejected and repeated (max 3) if `docker events --filter event=start` shows any other container start in the trace window. All 10 have a clean run (`swat4j/jdk8_debian10/dynamic/dynamic_runs.tsv`) |
| Native recall | 1 run per image |
| runc post-filter audit (busybox) | 3 runs, identical (28 syscalls) |
