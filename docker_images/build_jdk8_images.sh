#!/usr/bin/env bash
#
# Build the five Debian 10 + Temurin 8 images of 2_swat4j_vs_sysjava from
# dockerfiles/jdk8-buster/<app>/.
#
#   ./build_jdk8_images.sh                 # all five, pinned (default)
#   ./build_jdk8_images.sh storm jetty     # selected apps
#   ORIGINAL=1 ./build_jdk8_images.sh      # build the Dockerfiles exactly as written
#
# The Dockerfiles are kept exactly as they were used. Two of their inputs move
# over time: the base tag debian:buster-slim, and the Temurin download
# ("latest 8 GA"). By default this script pins both to what the shipped
# results were built with:
#   * debian:buster-slim is pulled by its digest and tagged locally before the build;
#   * the Temurin URL is rewritten, in a temporary copy of the build context,
#     to the exact release jdk8u504-b01.
# The application tarballs are versioned URLs already (ARG *_VERSION).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_REF="debian@sha256:bb3dc79fddbca7e8903248ab916bb775c96ec61014b3d02b4f06043b604726dc"
TEMURIN_LATEST='https://api.adoptium.net/v3/binary/latest/8/ga/linux/x64/jdk/hotspot/normal/eclipse?project=jdk'
TEMURIN_PINNED='https://api.adoptium.net/v3/binary/version/jdk8u504-b01/linux/x64/jdk/hotspot/normal/eclipse?project=jdk'
declare -A TAG=([storm]=storm:2.4.0-jdk8-buster [solr]=solr:8.7.0-jdk8-buster
                [elasticsearch]=elasticsearch:7.5.2-jdk8-buster [groovy]=groovy:4.0.0-jdk8-buster
                [jetty]=jetty:9.4.51-jdk8-buster)
APPS=("$@"); [ ${#APPS[@]} -gt 0 ] || APPS=(storm solr elasticsearch groovy jetty)

if [ -z "${ORIGINAL:-}" ]; then
    docker pull "$BASE_REF"
    docker tag "$BASE_REF" debian:buster-slim
fi
for app in "${APPS[@]}"; do
    tag="${TAG[$app]:?unknown app $app}"
    ctx="$HERE/dockerfiles/jdk8-buster/$app"
    if [ -z "${ORIGINAL:-}" ]; then
        tmp="$(mktemp -d)"; cp -a "$ctx/." "$tmp/"
        sed -i "s#${TEMURIN_LATEST}#${TEMURIN_PINNED}#g" "$tmp/Dockerfile"
        grep -q "jdk8u504-b01" "$tmp/Dockerfile" || { echo "Temurin URL not found in $app/Dockerfile"; exit 1; }
        ctx="$tmp"
    fi
    echo "== $tag"
    docker build -t "$tag" "$ctx"
    docker run --rm --entrypoint /opt/java/bin/java "$tag" -version 2>&1 | grep -i 'runtime environment'
    if [ -z "${ORIGINAL:-}" ]; then rm -rf "$ctx"; fi
done
