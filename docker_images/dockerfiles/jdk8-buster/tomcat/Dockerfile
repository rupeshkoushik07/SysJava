# Official tomcat:7.0 (7.0.109) is already Debian 10 (buster) but ships OpenJDK
# 8u292 (AdoptOpenJDK upstream build). Only the JDK is replaced: Temurin 8u504-b01,
# installed as in the other jdk8-buster Dockerfiles, goes to /opt/java and the
# old /usr/local/openjdk-8 is removed. Everything else, including the APR
# tomcat-native library built into the official image, is unchanged.
FROM debian:buster-slim AS jdk
RUN set -eux; \
    printf 'Acquire::Check-Valid-Until "false";\n' > /etc/apt/apt.conf.d/99no-check-valid-until; \
    sed -i 's|deb.debian.org/debian|archive.debian.org/debian|g; s|security.debian.org/debian-security|archive.debian.org/debian-security|g; /buster-updates/d' /etc/apt/sources.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl; \
    mkdir -p /opt/java; \
    curl -fsSL "https://api.adoptium.net/v3/binary/version/jdk8u504-b01/linux/x64/jdk/hotspot/normal/eclipse?project=jdk" \
        -o /tmp/temurin8.tar.gz; \
    tar -xzf /tmp/temurin8.tar.gz -C /opt/java --strip-components=1

FROM tomcat:7.0
COPY --from=jdk /opt/java /opt/java
ENV JAVA_HOME=/opt/java \
    JAVA_VERSION=8u504 \
    PATH=/usr/local/tomcat/bin:/opt/java/bin:/opt/java/jre/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
RUN set -eux; rm -rf /usr/local/openjdk-8; java -version; \
    catalina.sh configtest 2>&1 | grep -E 'Loaded( APR based)? Apache Tomcat Native library'
