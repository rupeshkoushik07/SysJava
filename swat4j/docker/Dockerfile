# Environment SWAT4J assumes: Ubuntu host with OpenJDK 8 at /usr/lib/jvm/java-8-openjdk-amd64
FROM ubuntu:18.04
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      openjdk-8-jdk binutils auditd python3 file && rm -rf /var/lib/apt/lists/*
