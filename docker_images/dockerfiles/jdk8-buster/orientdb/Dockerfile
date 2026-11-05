# Official orientdb:3.2.19 (Ubuntu 22.04, Temurin 8u372 JDK) rebased onto
# debian:buster-slim with Temurin 8 installed as in the other jdk8-buster
# Dockerfiles (pinned to 8u504-b01, the build the other five got). /orientdb is copied unchanged from the official image.
FROM orientdb:3.2.19 AS official

FROM debian:buster-slim

ENV JAVA_HOME=/opt/java \
    ORIENTDB_VERSION=3.2.19 \
    LANG=en_US.UTF-8 LANGUAGE=en_US:en LC_ALL=en_US.UTF-8 \
    PATH=/orientdb/bin:/opt/java/bin:/opt/java/jre/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

RUN set -eux; \
    printf 'Acquire::Check-Valid-Until "false";\n' > /etc/apt/apt.conf.d/99no-check-valid-until; \
    sed -i 's|deb.debian.org/debian|archive.debian.org/debian|g; s|security.debian.org/debian-security|archive.debian.org/debian-security|g; /buster-updates/d' /etc/apt/sources.list; \
    apt-get update; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates curl wget tzdata fontconfig locales procps; \
    echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen; locale-gen en_US.UTF-8; \
    mkdir -p /opt/java; \
    curl -fsSL "https://api.adoptium.net/v3/binary/version/jdk8u504-b01/linux/x64/jdk/hotspot/normal/eclipse?project=jdk" \
        -o /tmp/temurin8.tar.gz; \
    tar -xzf /tmp/temurin8.tar.gz -C /opt/java --strip-components=1; \
    rm /tmp/temurin8.tar.gz; \
    rm -rf /var/lib/apt/lists/*; \
    java -version

COPY --from=official /orientdb /orientdb

VOLUME ["/orientdb/backup", "/orientdb/databases", "/orientdb/config"]
WORKDIR /orientdb
EXPOSE 2424 2480
CMD ["server.sh"]
