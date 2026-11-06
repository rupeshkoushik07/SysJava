# Docker images

Every image used for the shipped results. `pull_ref` is the registry digest:
`docker pull <pull_ref>` gives the exact image. Built images have no registry
digest; their local image ID is recorded for identification.

| Tag | Folder | Obtained | OS | JDK | Pull reference (digest) | Image ID |
|---|---|---|---|---|---|---|
| `cassandra:5.0.8` | 1_latest_containers | official | Debian 12 | 17 | `cassandra@sha256:e32b183f147fd73606a5e7f455e9b7fe1047612ab35ee06b66eb056505fd2fa0` | `sha256:aad725cc07d7c45244f055f42a1e9ad031cf20d62a7ae131d835677dd9b4c594` |
| `zookeeper:3.9.5` | 1_latest_containers (also Storm's ZooKeeper) | official | Ubuntu 22.04 | 17.0.19 | `zookeeper@sha256:e12cace7b5fcfaadf17d6532e83fd8fe71fdf40ab73f22370ccc314bcf7a38b4` | `sha256:f8012ca9fc0179fe00de18ca202ac1d11a59435168c175658a59d727a1bc9026` |
| `tomcat:11.0.22` | 1_latest_containers | official tomcat:11.0, retagged | Ubuntu 24.04 | 25.0.3 | `tomcat@sha256:f8d2287df1bb2bf9b75a6acfc6d25a75b3a9044429906ff04e01533cfbafa028` | `sha256:59ab4ab47f49cf334534f4dc09ef8ff62a08a630f20499d34d81efe4811bbba1` |
| `solr:10.0.0` | 1_latest_containers | official | Ubuntu 24.04 | 25.0.3 | `solr@sha256:79b08a5fabda917e6d840c384485a7c5d0dcfe3a0ebcb5bf65c30278c3b53ade` | `sha256:43594516015d4c5bc5c179a09a24dfdbc0069fb0e9e3c9dce73a18d77382c492` |
| `groovy:5.0.6` | 1_latest_containers | official | Ubuntu 24.04 | 21.0.11 | `groovy@sha256:4eed25f51ec3a52c5f1517bae05c26846c0cc7c0d423186988bce0e7c8502e11` | `sha256:01e7346692df76149ed9bc6a6802e2cf70fd0932c807392a8c3392cedd2bc16a` |
| `orientdb:3.2.53` | 1_latest_containers | official orientdb:latest, retagged | Ubuntu 26.04 | 8u492-b09 | `orientdb@sha256:004245009c515f7959ead72082748ba4b96eaa50221aeb09e3b515647ad29fb9` | `sha256:8e4c714969f34bb57cae1b475ca053e63664420069cbf8410563b6d9d7c91da6` |
| `jetty:12.1.10` | 1_latest_containers | official | Ubuntu 26.04 | 25.0.3 | `jetty@sha256:518a0d1c37327522b24759390e30ee8b52cb8e5053daea03fe45b59881a658b7` | `sha256:2b488a60aa51bd130a69881ed6ce440a046ea97aa9c1d14abaa380af4af61f17` |
| `elasticsearch:7.1.0` | 1_latest_containers | docker.elastic.co/elasticsearch/elasticsearch:7.1.0, retagged | CentOS 7 | 12 (bundled) | `docker.elastic.co/elasticsearch/elasticsearch@sha256:802b6a299260dbaf21a9c57e3a634491ff788a1ea13a51598d4cd105739509c4` | `sha256:12ad640a1ec0484ee7eac455e6b924fb01a1fc88ca01d5a6d90cfa7554ab4568` |
| `storm:2.8.8` | 1_latest_containers | official storm:latest, retagged | Ubuntu 26.04 | 17.0.19 | `storm@sha256:6c89d248d7c1ecf5a13c8ad1efade66739df227fbfa151243292a6d2865d63a7` | `sha256:a88e5583f44ec6f760d2392a4469a775744f2b67366b14082c3afd14974e2472` |
| `jruby:10.1.0.0` | 1_latest_containers | official | Ubuntu 24.04 | 21.0.11 | `jruby@sha256:1cf95cc01799f6698480bbbc68553a1f64993835d8e872c49ccc3287c05ceefb` | `sha256:f2334c8daa138c7301f67e8b0216fe9e3ad9457120b3a1df03c92ccba77d0f7d` |
| `storm:2.4.0-jdk8-buster` | 2_swat4j_vs_sysjava | built: dockerfiles/jdk8-buster/storm | Debian 10 | Temurin 8u504-b01 | `built-locally` | `sha256:56d63c0166635eb968ef6bc078135f17f1579bb8c500cb04d640eb8061e84127` |
| `solr:8.7.0-jdk8-buster` | 2_swat4j_vs_sysjava | built: dockerfiles/jdk8-buster/solr | Debian 10 | Temurin 8u504-b01 | `built-locally` | `sha256:096ad044a86ac2cfa22758612f5d68b81e911c5c921d4fb5a1475372cc0aa03d` |
| `elasticsearch:7.5.2-jdk8-buster` | 2_swat4j_vs_sysjava | built: dockerfiles/jdk8-buster/elasticsearch | Debian 10 | Temurin 8u504-b01 | `built-locally` | `sha256:9dcdb3711d1bb2ffc315f067d9a0a37b8336964c717605abdba9514e95c916c5` |
| `groovy:4.0.0-jdk8-buster` | 2_swat4j_vs_sysjava | built: dockerfiles/jdk8-buster/groovy | Debian 10 | Temurin 8u504-b01 | `built-locally` | `sha256:854fc6e6153abca0007414062ee76c389282b0c85cddfa50c6443069a3a0d276` |
| `jetty:9.4.51-jdk8-buster` | 2_swat4j_vs_sysjava | built: dockerfiles/jdk8-buster/jetty | Debian 10 | Temurin 8u504-b01 | `built-locally` | `sha256:fd179e5c13cdbfcdad43408baf2dfaabf59a2590dca578eda575b79a1c72c54a` |
| `zookeeper:3.7` | 2_swat4j_vs_sysjava (Storm's ZooKeeper) | official | Ubuntu 22.04 | 11.0.25 | `zookeeper@sha256:6c5ec2f492ab361c4adfe02ea87ea928a3461e1897e81868e09ee9ffbfac8e58` | `sha256:314372177cd67878964b3cfb200f05e4ffd424f260629c69425b415bd4c20add` |
| `zookeeper:3.4.14-jdk8-buster` | 2_swat4j_vs_sysjava | built: dockerfiles/jdk8-buster/zookeeper | Debian 10 | Temurin 8u504-b01 | `built-locally` | `sha256:4dbf574e40c4132ce23fa9d8c5691f4fd3ff431438c65a4c79859ec4b6d8e7ce` |
| `zookeeper:3.4.14` | build stage of dockerfiles/jdk8-buster/zookeeper | official | Debian 10 | 8u292 | `zookeeper@sha256:3882d9493d387ba77b7b69e2a031b9396477ec29483d51ceaed645c1389182e5` | `sha256:4b03fe5b3f6433c4a26511a524323228f44c70460d592cae4704d93c922fb8e4` |
| `tomcat:7.0-jdk8-buster` | 2_swat4j_vs_sysjava | built: dockerfiles/jdk8-buster/tomcat | Debian 10 | Temurin 8u504-b01 | `built-locally` | `sha256:651fe3f49c103545f1c2b76d91229cd042139401d3ec54a181ee5a28588b2682` |
| `tomcat:7.0` | build stage of dockerfiles/jdk8-buster/tomcat | official | Debian 10 | 8u292 | `tomcat@sha256:f7d37d248d0eacec1e5995736234c9c22155626fcb27ea3ead13b9db24e698f7` | `sha256:9dfd74e6bc2f5a477649be71bec187dce1c04cccecaca286d5e6604e9f8d2afc` |
| `cassandra:3.0.29-jdk8-buster` | 2_swat4j_vs_sysjava | built: dockerfiles/jdk8-buster/cassandra | Debian 10 | Temurin 8u504-b01 | `built-locally` | `sha256:ad00034649725f9bc294bd20537a1f09c7ea6ad963a170a57645d001a55eecbe` |
| `cassandra:3.0.29` | build stage of dockerfiles/jdk8-buster/cassandra | official | Ubuntu 22.04 | 8u402-b06 | `cassandra@sha256:74303adb69dc9b649600a3f74f90368b0954f952409964a79a2d33310f2e0ecd` | `sha256:a6dad7878b765d6f04777f949c635d65260fec68ca9c5f685fd33522b7393a5b` |
| `orientdb:3.2.19-jdk8-buster` | 2_swat4j_vs_sysjava | built: dockerfiles/jdk8-buster/orientdb | Debian 10 | Temurin 8u504-b01 | `built-locally` | `sha256:970915ce0031ab81196602a050d13246cd1fd323ccd14bb87487ef5f89ee00c3` |
| `orientdb:3.2.19` | build stage of dockerfiles/jdk8-buster/orientdb | official | Ubuntu 22.04 | 8u372-b07 | `orientdb@sha256:396badf7f07a2b758c12d6c348fa3cfa409f9a3f1c66773698de67da5440540d` | `sha256:000938305998c1d9d2c0ac8c2f68b1ebbf2beda1b7160e90b54c0ba377c940d2` |
| `jruby:9.4.2.0-jdk8-buster` | 2_swat4j_vs_sysjava | built: dockerfiles/jdk8-buster/jruby | Debian 10 | Temurin 8u504-b01 | `built-locally` | `sha256:5f18769f99bbee4805f1858a49d0659ae0972ee2206b3c1c0affa1ade4f408a9` |
| `jruby:9.4.2.0` | build stage of dockerfiles/jdk8-buster/jruby | official | Ubuntu 20.04 | 8u372-b07 | `jruby@sha256:5bf04ca61daa2efa2aae1c9e4c70ffa4da84e7004f27e519ef81e59ce390f490` | `sha256:5ed6083138c3fd5d8bf44e2c2480bffdf58c876502fb8d4ce45f7384a2422e7c` |
| `debian:buster-slim` | base of the ten built images | official | Debian 10 | - | `debian@sha256:bb3dc79fddbca7e8903248ab916bb775c96ec61014b3d02b4f06043b604726dc` | `sha256:e1a7bb630c8baa947c5430a7f0965ef6afe71e88e90547aced2e601a89b68399` |
