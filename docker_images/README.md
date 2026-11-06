# Docker images

These are all the container images behind the results, with the digest of each
so that the exact image can be fetched again.

| File | Content |
|---|---|
| [`IMAGES.md`](IMAGES.md) | Every image: tag, results folder, how it was obtained, OS, JDK, registry digest, image ID |
| `images.tsv` | The same as a tab-separated file. The `reproduce.sh` scripts read it |
| `dockerfiles/jdk8-buster/<app>/` | Dockerfiles of the ten images rebuilt on Debian 10 + JDK 8, exactly as used |
| `build_jdk8_images.sh` | Builds those ten images with their moving inputs pinned |
| `ENVIRONMENT.md`, `environment.json` | Host, kernel, Docker, containerd, runc, libseccomp and tool versions of the runs |

## Two kinds of images

1. **Official images, newer versions** (`1_latest_containers`), pulled by digest.
   Four are retagged so that the tag carries the version: `tomcat:11.0` →
   `tomcat:11.0.22`, `orientdb:latest` → `orientdb:3.2.53`, `storm:latest` →
   `storm:2.8.8`, `docker.elastic.co/elasticsearch/elasticsearch:7.1.0` →
   `elasticsearch:7.1.0`.
2. **Rebuilt JDK 8 images** (`2_swat4j_vs_sysjava`), `<app>:<version>-jdk8-buster`.
   SWAT4J needs JDK 8, so each application was rebuilt on `debian:buster-slim`
   with Eclipse Temurin 8u504-b01 at `/opt/java`, keeping the official
   application distribution, layout, user and start command. Debian 10 packages
   come from `archive.debian.org`. Groovy keeps `groovysh` running so the
   container stays up for the capture.

## Pulling by digest

```bash
docker pull tomcat@sha256:<digest from IMAGES.md>
docker tag  tomcat@sha256:<digest> tomcat:11.0.22
```

`1_latest_containers/reproduce.sh` and `2_swat4j_vs_sysjava/reproduce.sh` do
this automatically for every image that is not present locally.

## Building the rebuilt images

```bash
./build_jdk8_images.sh                # all ten
./build_jdk8_images.sh storm jetty    # selected
ORIGINAL=1 ./build_jdk8_images.sh     # the Dockerfiles exactly as written, nothing pinned
```

The Dockerfiles take inputs that move over time: the tag `debian:buster-slim`,
the official images some build FROM, and, in five of them, the Temurin download
("latest 8 GA"). By default the script pins all of them to what the shipped
results were built with:

* `debian:buster-slim` is pulled as
  `debian@sha256:bb3dc79fddbca7e8903248ab916bb775c96ec61014b3d02b4f06043b604726dc`;
* official base images are pulled by the digest in `images.tsv`;
* Temurin is fetched as release `jdk8u504-b01`
  (`https://api.adoptium.net/v3/binary/version/jdk8u504-b01/...`).

The Debian 10 packages installed by `apt-get` come from `archive.debian.org`,
which no longer changes. A rebuilt image still gets a new image ID, since layers
carry timestamps. The IDs in `IMAGES.md` identify the images actually used;
the images themselves were saved with `docker save` (5 GB) but are not in this
repository.
