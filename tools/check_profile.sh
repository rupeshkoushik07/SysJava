#!/usr/bin/env bash
#
# Run an image's container under a seccomp profile, as the last stage of the pipeline does
# (stage 11 for the latest images, stage 10 for the JDK 8 images). Needs Docker.
#
#   tools/check_profile.sh <image folder name> <profile.json> <log>
#
# The image, its run arguments, command and readiness marker are those of the table's driver
# (the case block of run_latest_target.sh or run_jdk8_target.sh); the check is the table's
# scripts/verify_seccomp_profile.sh: the workload runs once without and once with the profile,
# and RESULT=PASS needs ready + still running + the HTTP probe + no extra EPERM lines.
set -euo pipefail
ART="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
T="${1:?image folder name}"; PROFILE="$(realpath "${2:?profile}")"; LOG="${3:?log}"

case "$T" in
    *-jdk8-buster) TABLE="$ART/2_swat4j_vs_sysjava"; DRIVER=run_jdk8_target.sh
                   NET=et-jdk8-net; ZK_NAME=et-jdk8-zookeeper; ZK_IMAGE=zookeeper:3.7 ;;
    *)             TABLE="$ART/1_latest_containers"; DRIVER=run_latest_target.sh
                   NET=et-latest-net; ZK_NAME=et-latest-zookeeper; ZK_IMAGE=zookeeper:3.9.5 ;;
esac
LOGFILE=""
# IMAGE, RUN_ARGS, CMD, MARKER (and LOGFILE) for $T, from the driver
eval "$(sed -n '/^case "\$T" in/,/^esac/p' "$TABLE/scripts/$DRIVER")"

have() { docker image inspect "$1" >/dev/null 2>&1; }
pin() {  # pull a tag by the digest of the shipped results (docker_images/images.tsv)
    local ref; ref="$(awk -F'\t' -v t="$1" '$1==t{print $2}' "$ART/docker_images/images.tsv")"
    case "$ref" in *@sha256:*) docker pull "$ref" && docker tag "$ref" "$1" ;; *) docker pull "$1" ;; esac
}
if ! have "$IMAGE"; then
    if [[ "$IMAGE" == *-jdk8-buster ]]; then bash "$ART/docker_images/build_jdk8_images.sh" "${IMAGE%%:*}"
    else pin "$IMAGE"; fi
fi
# Storm's nimbus halts without ZooKeeper: the drivers start it on their network in stage 1.
if [[ " ${RUN_ARGS[*]} " == *" --network $NET "* ]]; then
    have "$ZK_IMAGE" || pin "$ZK_IMAGE"
    docker network inspect "$NET" >/dev/null 2>&1 || docker network create "$NET" >/dev/null
    [ "$(docker inspect -f '{{.State.Running}}' "$ZK_NAME" 2>/dev/null)" = true ] || {
        docker rm -f "$ZK_NAME" >/dev/null 2>&1 || true
        docker run -d --name "$ZK_NAME" --network "$NET" --network-alias zookeeper "$ZK_IMAGE" >/dev/null; }
fi

VERIFY_MARKER="$MARKER" VERIFY_LOGFILE="$LOGFILE" bash "$TABLE/scripts/verify_seccomp_profile.sh" \
    "$T" "$IMAGE" "$PROFILE" "$LOG" -- "${RUN_ARGS[@]}" -- "${CMD[@]}"
