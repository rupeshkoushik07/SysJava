#!/bin/bash
# Copy from each JDK 8 image the files SWAT4J's static step reads: the loader, the system library
# directories, /etc/ld.so.conf*, the JDK's native libraries (/opt/java/jre/lib/amd64) and the image's
# LD_LIBRARY_PATH directories. Output: rootfs/<image>/... (read only afterwards)
set -euo pipefail
cd "$(dirname "$0")"
for t in zookeeper_3.4.14 tomcat_7.0 cassandra_3.0.29 jetty_9.4.51 storm_2.4.0 orientdb_3.2.19 elasticsearch_7.5.2 solr_8.7.0 groovy_4.0.0 jruby_9.4.2.0; do
  img="${t%%_*}:${t#*_}-jdk8-buster"; T="$t-jdk8-buster"; r=rootfs/$T
  rm -rf "$r"; mkdir -p "$r/opt/java/jre/lib" "$r/usr/lib" "$r/etc"
  c=$(docker create "$img")
  docker cp -q "$c:/lib" "$r/lib"
  docker cp -q "$c:/lib64" "$r/lib64"
  docker cp -q "$c:/usr/lib/x86_64-linux-gnu" "$r/usr/lib/x86_64-linux-gnu"
  docker cp -q "$c:/etc/ld.so.conf" "$r/etc/ld.so.conf"
  docker cp -q "$c:/etc/ld.so.conf.d" "$r/etc/ld.so.conf.d"
  docker cp -q -L "$c:/opt/java/jre/lib/amd64" "$r/opt/java/jre/lib/amd64"
  ldp=$(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$img" | sed -n 's/^LD_LIBRARY_PATH=//p')
  for d in ${ldp//:/ }; do mkdir -p "$r$(dirname "$d")"; docker cp -q -L "$c:$d" "$r$d"; done
  echo "$ldp" > "$r/LD_LIBRARY_PATH"
  docker rm "$c" >/dev/null
  echo "$T: $(du -sh "$r" | cut -f1); ld.so.conf.d: $(cat "$r"/etc/ld.so.conf.d/*.conf 2>/dev/null | grep -v '^#' | tr '\n' ' '); LD_LIBRARY_PATH=$ldp"
done

# SWAT4J parses objdump labels of the form <Java_...@@SUNWprivate_1.1>, i.e. a JDK packaged without .symtab
# (Ubuntu's OpenJDK, which the paper run read). Temurin keeps .symtab, so objdump prints names without the
# version and SWAT4J's parser stops. jdk_dynsym/ is the image's jre/lib/amd64 with only .symtab/.strtab
# removed (strip --strip-all keeps .dynsym and every byte of code): same code, Ubuntu-like packaging.
for r in rootfs/*-jdk8-buster; do
  rm -rf "$r/jdk_dynsym"; cp -a "$r/opt/java/jre/lib/amd64" "$r/jdk_dynsym"
  find "$r/jdk_dynsym" -name '*.so' -type f -exec strip --strip-all {} +
  echo "$(basename $r): jdk_dynsym $(find "$r/jdk_dynsym" -name '*.so' -type f | wc -l) libraries"
done
