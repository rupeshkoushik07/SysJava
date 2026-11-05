# Added binaries (not captured)

- `cp` — added 2026-11-05 ~18:10 (user decision "Analyse cp, rerun 9-11").
  /opt/solr/docker/scripts/init-var-solr runs `cp -a .../log4j2.xml "$DIR/log4j2.xml"` only when
  /var/solr/log4j2.xml does not exist (first start). sysdig_unified.sh captures a `docker stop` +
  `docker start` of the already-initialised container, so this branch never ran during capture and
  `cp` is missing from binaries_unique; the fresh stage-11 verify container runs it (it failed with
  EPERM on utimensat: "cp: preserving times for '/var/solr/log4j2.xml'").
  Source: /usr/bin/cp from image solr:10.0.0 (coreutils 9.4-3ubuntu6.2, Ubuntu noble), Build ID
  d5f1c71e79de1315efa129a60476c4993a56b77e; debug symbols from Launchpad coreutils-dbgsym
  9.4-3ubuntu6.2 (debuginfod had none), Build-ID verified, merged with eu-unstrip + objcopy
  --strip-debug like every other binary. Analysed with automate_syscall_analysis.sh --binaries-only
  (same SysPart build and executable start-function rule as solr's other binaries).
