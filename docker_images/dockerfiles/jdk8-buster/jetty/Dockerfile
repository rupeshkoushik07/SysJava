# Dockerfile.jetty-9.4.51-openjdk8 rebased from eclipse-temurin:8-jre-jammy
# (Ubuntu 22.04) onto debian:buster-slim, installing Temurin 8 exactly as the
# elasticsearch/groovy/solr temurin8 Dockerfiles do. Everything else unchanged.
FROM debian:buster-slim

ARG JETTY_VERSION=9.4.51.v20230217
ENV JAVA_HOME=/opt/java \
    JETTY_HOME=/opt/jetty \
    JETTY_BASE=/var/lib/jetty \
    PATH=/opt/java/bin:/opt/java/jre/bin:$PATH

RUN set -eux; \
    printf 'Acquire::Check-Valid-Until "false";\n' > /etc/apt/apt.conf.d/99no-check-valid-until; \
    sed -i 's|deb.debian.org/debian|archive.debian.org/debian|g; s|security.debian.org/debian-security|archive.debian.org/debian-security|g; /buster-updates/d' /etc/apt/sources.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl tar; \
    mkdir -p /opt/java; \
    curl -fsSL "https://api.adoptium.net/v3/binary/latest/8/ga/linux/x64/jdk/hotspot/normal/eclipse?project=jdk" \
        -o /tmp/temurin8.tar.gz; \
    tar -xzf /tmp/temurin8.tar.gz -C /opt/java --strip-components=1; \
    curl -fSL "https://repo1.maven.org/maven2/org/eclipse/jetty/jetty-distribution/${JETTY_VERSION}/jetty-distribution-${JETTY_VERSION}.tar.gz" -o /tmp/jetty.tar.gz; \
    mkdir -p "${JETTY_HOME}" "${JETTY_BASE}"; \
    tar -xzf /tmp/jetty.tar.gz -C "${JETTY_HOME}" --strip-components=1; \
    rm /tmp/jetty.tar.gz /tmp/temurin8.tar.gz; \
    useradd -r -m -d "${JETTY_BASE}" -s /usr/sbin/nologin jetty; \
    mkdir -p /tmp/jetty; \
    chown -R jetty:jetty "${JETTY_HOME}" "${JETTY_BASE}" /tmp/jetty; \
    apt-get purge -y --auto-remove curl; \
    rm -rf /var/lib/apt/lists/*

# Set after the apt step: dpkg maintainer scripts fail when TMPDIR is missing.
ENV TMPDIR=/tmp/jetty

USER jetty
WORKDIR ${JETTY_BASE}

RUN java -jar "${JETTY_HOME}/start.jar" --add-to-start=http,deploy

EXPOSE 8080

CMD ["java", "-jar", "/opt/jetty/start.jar"]
