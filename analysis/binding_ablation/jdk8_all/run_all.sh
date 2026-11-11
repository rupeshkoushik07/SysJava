#!/bin/bash
# No-binding (arm A) SysPart runs for every distinct library of the ten JDK 8 images (targets/ from
# make_targets.py), one image after another, JOBS runs in parallel. Output: results/A/<img>/<lib>/.
# SYSPART_APP=<SysPart analysis/app build dir> is required (see syspart/README.md).
# 24 GB and 4 h per run were enough for every library (largest: libc-2.28, librocksdbjni).
set -euo pipefail
cd "$(dirname "$0")"
: "${SYSPART_APP:?set SYSPART_APP to the SysPart analysis/app directory}"
WORK=${WORK:-$PWD/work}; JOBS=${JOBS:-2}
for f in targets/*.tsv; do
  img=$(basename "$f" .tsv)
  RESULTS=$WORK/$img SYMBOLIZED=1 LEAN=1 TARGETS=$PWD/$f ARMS=A OUT_DIR=$WORK/runs/$img SYSPART_APP=$SYSPART_APP \
    NICE=${NICE:-10} JOB_MEM_GB=${JOB_MEM_GB:-24} JOB_TIMEOUT=${JOB_TIMEOUT:-14400} ../run_ablation.sh "$img" "$JOBS"
  for d in "$WORK/runs/$img/A"/*/; do
    o=results/A/$img/$(basename "$d"); mkdir -p "$o"
    cp "$d/syscalls.txt" "$d/startfuncs_with_addr.txt" "$o/"
  done
done
echo "all done $(date)"
