# Official cassandra:3.0.29 (Ubuntu 22.04, Temurin 8u402 JRE) rebased onto
# debian:buster-slim with Temurin 8 installed as in the other jdk8-buster
# Dockerfiles (pinned to 8u504-b01, the build the other five got). Cassandra, its config, entrypoint and gosu are copied unchanged
# from the official image; its runtime packages are installed from Debian 10.
FROM cassandra:3.0.29 AS official

FROM debian:buster-slim

ENV JAVA_HOME=/opt/java \
    CASSANDRA_HOME=/opt/cassandra \
    CASSANDRA_CONF=/etc/cassandra \
    CASSANDRA_VERSION=3.0.29 \
    LANG=en_US.UTF-8 LANGUAGE=en_US:en LC_ALL=en_US.UTF-8 \
    PATH=/opt/cassandra/bin:/opt/java/bin:/opt/java/jre/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

RUN set -eux; \
    printf 'Acquire::Check-Valid-Until "false";\n' > /etc/apt/apt.conf.d/99no-check-valid-until; \
    sed -i 's|deb.debian.org/debian|archive.debian.org/debian|g; s|security.debian.org/debian-security|archive.debian.org/debian-security|g; /buster-updates/d' /etc/apt/sources.list; \
    apt-get update; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates curl tzdata locales \
        libjemalloc2 procps python2 iproute2 numactl; \
    echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen; locale-gen en_US.UTF-8; \
    mkdir -p /opt/java; \
    curl -fsSL "https://api.adoptium.net/v3/binary/version/jdk8u504-b01/linux/x64/jdk/hotspot/normal/eclipse?project=jdk" \
        -o /tmp/temurin8.tar.gz; \
    tar -xzf /tmp/temurin8.tar.gz -C /opt/java --strip-components=1; \
    rm /tmp/temurin8.tar.gz; \
    apt-get purge -y --auto-remove curl; \
    rm -rf /var/lib/apt/lists/*; \
    libjemalloc="$(readlink -e /usr/lib/*/libjemalloc.so.2)"; \
    ln -sT "$libjemalloc" /usr/local/lib/libjemalloc.so; \
    ldconfig; \
    groupadd -r cassandra --gid=999; \
    useradd -r -g cassandra --uid=999 cassandra

COPY --from=official /usr/local/bin/gosu /usr/local/bin/gosu
COPY --from=official /usr/local/bin/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
COPY --from=official --chown=cassandra:cassandra /opt/cassandra /opt/cassandra
COPY --from=official --chown=cassandra:cassandra /etc/cassandra /etc/cassandra

RUN set -eux; \
    ln -s usr/local/bin/docker-entrypoint.sh /docker-entrypoint.sh; \
    mkdir -p /var/lib/cassandra /var/log/cassandra; \
    chown -R cassandra:cassandra /var/lib/cassandra /var/log/cassandra; \
    chmod 1777 /var/lib/cassandra /var/log/cassandra /etc/cassandra; \
    gosu --version; java -version; cassandra -v

VOLUME /var/lib/cassandra
ENTRYPOINT ["docker-entrypoint.sh"]
EXPOSE 7000 7001 7199 9042 9160
CMD ["cassandra", "-f"]
