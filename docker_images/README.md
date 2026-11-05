# Docker images

These are all the container images behind the results, with the digest of each
so that the exact image can be fetched again.

| File | Content |
|---|---|
| [`IMAGES.md`](IMAGES.md) | Every image: tag, results folder, how it was obtained, OS, JDK, registry digest, image ID |
| `images.tsv` | The same as a tab-separated file. The `reproduce.sh` scripts read it |
| `dockerfiles/jdk8-buster/<app>/` | Dockerfiles (and entrypoints) of the five images rebuilt on Debian 10 + JDK 8, exactly as used |
| `build_jdk8_images.sh` | Builds those five images with their moving inputs pinned |

## Three kinds of images

1. **Official images, newer versions** (`1_latest_containers`). These are pulled
   from Docker Hub. Elasticsearch comes from `docker.elastic.co`. Four are
   retagged so that the tag carries the version: `tomcat:11.0` → `tomcat:11.0.22`,
   `orientdb:latest` → `orientdb:3.2.53`, `storm:latest` → `storm:2.8.8`, and
   `docker.elastic.co/elasticsearch/elasticsearch:7.1.0` → `elasticsearch:7.1.0`.
   The pipeline names its output folders after the image tag.
2. **Official JDK 8 images** (`2_swat4j_vs_sysjava`): `zookeeper:3.4.14`,
   `tomcat:7.0`, `cassandra:3.0.29`, `orientdb:3.2.19`, `jruby:9.4.2.0`. They
   already ship JDK 8 and are used unchanged.
3. **Rebuilt images** (`2_swat4j_vs_sysjava`): Storm 2.4.0, Solr 8.7.0,
   Elasticsearch 7.5.2, Groovy 4.0.0, Jetty 9.4.51. Their official images ship
   JDK 11, 13 or 17 on various distributions, but SWAT4J needs JDK 8. Each was
   rebuilt from `debian:buster-slim` with Eclipse Temurin 8, keeping the official
   application distribution, layout, user and start command. The changes are:
   * base image `debian:buster-slim`, with apt pointed at `archive.debian.org`
     (Debian 10 is archived);
   * JDK: Temurin 8 unpacked to `/opt/java`, in place of the bundled or
     distribution JDK (Elasticsearch's bundled `jdk/` is removed);
   * the application tarball is downloaded at the pinned version (`ARG *_VERSION`);
   * Groovy keeps `groovysh` running (`groovy-hold`) so the container stays up for
     the capture;
   * Jetty sets `TMPDIR` after the apt step.

## Pulling by digest

```bash
docker pull tomcat@sha256:<digest from IMAGES.md>
docker tag  tomcat@sha256:<digest> tomcat:11.0.22
```

`1_latest_containers/reproduce.sh` and `2_swat4j_vs_sysjava/reproduce.sh` do
this automatically for every image that is not present locally.

## Building the rebuilt images

```bash
./build_jdk8_images.sh                # all five
./build_jdk8_images.sh storm jetty    # selected
ORIGINAL=1 ./build_jdk8_images.sh     # the Dockerfiles exactly as written, nothing pinned
```

The Dockerfiles take two inputs that move over time: the tag
`debian:buster-slim` and the Temurin download ("latest 8 GA"). By default the
script pins both to what the shipped results were built with:

* `debian:buster-slim` is pulled as
  `debian@sha256:bb3dc79fddbca7e8903248ab916bb775c96ec61014b3d02b4f06043b604726dc`;
* Temurin is fetched as release `jdk8u504-b01`
  (`https://api.adoptium.net/v3/binary/version/jdk8u504-b01/...`).

The Debian 10 packages installed by `apt-get` come from `archive.debian.org`,
which no longer changes. A rebuilt image still gets a new image ID, since layers
carry timestamps. The IDs in `IMAGES.md` identify the images actually used.
