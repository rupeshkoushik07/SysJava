# Dockerfile.storm-2.4.0-temurin8 rebased from eclipse-temurin:8-jre-jammy
# (Ubuntu 22.04) onto debian:buster-slim, installing Temurin 8 exactly as the
# elasticsearch/groovy/solr temurin8 Dockerfiles do. Everything else unchanged.
FROM debian:buster-slim

ARG STORM_VERSION=2.4.0
ARG STORM_DIST_URL=https://archive.apache.org/dist/storm/apache-storm-${STORM_VERSION}/apache-storm-${STORM_VERSION}.tar.gz

ENV JAVA_HOME=/opt/java \
    STORM_HOME=/opt/storm \
    STORM_CONF_DIR=/opt/storm/conf \
    STORM_LOCAL_DIR=/var/lib/storm \
    PATH=/opt/java/bin:/opt/java/jre/bin:/opt/storm/bin:$PATH

RUN set -eux; \
    printf 'Acquire::Check-Valid-Until "false";\n' > /etc/apt/apt.conf.d/99no-check-valid-until; \
    sed -i 's|deb.debian.org/debian|archive.debian.org/debian|g; s|security.debian.org/debian-security|archive.debian.org/debian-security|g; /buster-updates/d' /etc/apt/sources.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl gosu procps python3 tar tini; \
    ln -sf /usr/bin/python3 /usr/local/bin/python; \
    rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    mkdir -p /opt/java "${STORM_HOME}" "${STORM_LOCAL_DIR}"; \
    curl -fsSL "https://api.adoptium.net/v3/binary/latest/8/ga/linux/x64/jdk/hotspot/normal/eclipse?project=jdk" \
        -o /tmp/temurin8.tar.gz; \
    tar -xzf /tmp/temurin8.tar.gz -C /opt/java --strip-components=1; \
    curl -fSL "${STORM_DIST_URL}" -o /tmp/apache-storm.tar.gz; \
    tar -xzf /tmp/apache-storm.tar.gz -C "${STORM_HOME}" --strip-components=1; \
    rm /tmp/apache-storm.tar.gz /tmp/temurin8.tar.gz; \
    groupadd -r storm; \
    useradd -r -g storm -d "${STORM_LOCAL_DIR}" -s /usr/sbin/nologin storm; \
    chown -R storm:storm "${STORM_HOME}" "${STORM_LOCAL_DIR}"

RUN set -eux; \
    { \
      echo "storm.zookeeper.servers:"; \
      echo "  - \"zookeeper\""; \
      echo "nimbus.seeds: [\"nimbus\"]"; \
      echo "storm.local.dir: \"${STORM_LOCAL_DIR}\""; \
      echo "supervisor.slots.ports:"; \
      echo "  - 6700"; \
      echo "  - 6701"; \
      echo "  - 6702"; \
      echo "  - 6703"; \
      echo "ui.port: 8080"; \
    } > "${STORM_CONF_DIR}/storm.yaml" \
    && chown storm:storm "${STORM_CONF_DIR}/storm.yaml"

WORKDIR ${STORM_HOME}

EXPOSE 6627 8080 6700 6701 6702 6703

# Debian packages tini as /usr/bin/tini, as Ubuntu does.
ENTRYPOINT ["tini", "--", "gosu", "storm", "storm"]
CMD ["version"]
