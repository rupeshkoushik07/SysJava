| | Zookeeper 3.4.14<br>JDK 8u504<br>Debian 10 | Tomcat 7.0<br>JDK 8u504<br>Debian 10 | Cassandra 3.0.29<br>JDK 8u504<br>Debian 10 | Jetty 9.4.51<br>JDK 8u504<br>Debian 10 | Storm 2.4.0<br>JDK 8u504<br>Debian 10 | OrientDB 3.2.19<br>JDK 8u504<br>Debian 10 | Elasticsearch 7.5.2<br>JDK 8u504<br>Debian 10 | Solr 8.7.0<br>JDK 8u504<br>Debian 10 | Groovy 4.0.0<br>JDK 8u504<br>Debian 10 | JRuby 9.4.2.0<br>JDK 8u504<br>Debian 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| **Native Method Resolution** | | | | | | | | | | |
| JNI Total Natives | 495 | 816 | 975 | 353 | 1884 | 700 | 626 | 980 | 588 | 598 |
| SysJava Resolved | 484 | 792 | 903 | 352 | 1835 | 684 | 609 | 967 | 541 | 587 |
| ↳ JNI Static (Java_*) | 317 | 564 | 596 | 185 | 1347 | 498 | 427 | 645 | 360 | 416 |
| ↳ Partial (_1/$/__) | 4 | 59 | 31 | 2 | 65 | 18 | 14 | 8 | 7 | 6 |
| ↳ JNI Dynamic (RegisterNatives) | 119 | 122 | 226 | 119 | 366 | 123 | 121 | 261 | 122 | 120 |
| ↳ JVM | 44 | 47 | 45 | 46 | 47 | 45 | 47 | 47 | 52 | 45 |
| ↳ JFR/Netty | 0 | 0 | 5 | 0 | 10 | 0 | 0 | 6 | 0 | 0 |
| ↳ Platform / Intrinsic | 10 | 21 | 71 | 0 | 46 | 8 | 16 | 10 | 39 | 3 |
| ↳ Not Found | 1 | 3 | 1 | 1 | 3 | 8 | 1 | 3 | 8 | 8 |
| SWAT4J Natives Found (JTracer) | 236 | 614 | 686 | 225 | 1529 | 519 | 368 | 613 | 334 | 448 |
| SWAT4J Resolved | 129 | 433 | 408 | 124 | 283 | 351 | 174 | 298 | 174 | 330 |
| ↳ SWAT4J JNI Static (Java_*) | 93 | 394 | 264 | 86 | 140 | 313 | 135 | 154 | 133 | 291 |
| ↳ JNI Partial/Heuristic | 0 | 0 | 107 | 0 | 104 | 0 | 0 | 104 | 0 | 0 |
| ↳ JVM Source Code | 36 | 39 | 37 | 38 | 39 | 38 | 39 | 40 | 41 | 39 |
| ↳ Not Found | 107 | 181 | 278 | 101 | 1246 | 168 | 194 | 315 | 160 | 118 |
| **Syscall Allowlist (SysJava only)** | | | | | | | | | | |
| Java Lib Syscalls | 108 | 124 | 124 | 92 | 125 | 111 | 113 | 127 | 109 | 95 |
| Container Binary Syscalls | 111 | 92 | 140 | 63 | 101 | 83 | 114 | 111 | 105 | 84 |
| Go Whitelist (Δ) | 36 | 35 | 24 | 51 | 26 | 40 | 31 | 28 | 37 | 43 |
| Unmapped Lib Syscalls (Δ) | 18 | 0 | 41 | 10 | 2 | 10 | 11 | 20 | 19 | 10 |
| Total Syscalls | 190 | 170 | 230 | 157 | 172 | 173 | 183 | 199 | 189 | 167 |
| **SWAT4J Syscall Comparison** | | | | | | | | | | |
| SWAT4J Java Lib Syscalls | 104 | 105 | 124 | 104 | 116 | 105 | 102 | 113 | 108 | 104 |
| SWAT4J Dynamic Syscalls | 128 | 127 | 141 | 128 | 137 | 129 | 137 | 136 | 130 | 128 |
| SWAT4J Total (Static ∪ Dynamic) | 171 | 170 | 182 | 171 | 178 | 169 | 174 | 175 | 175 | 170 |
| SysJava ∩ SWAT4J | 136 | 134 | 163 | 125 | 139 | 133 | 139 | 146 | 140 | 133 |
| SysJava only | 54 | 36 | 67 | 32 | 33 | 40 | 44 | 53 | 49 | 34 |
| SWAT4J only | 35 | 36 | 19 | 46 | 39 | 36 | 35 | 29 | 35 | 37 |
| **Dynamic Capture Artefacts** | | | | | | | | | | |
| Libraries Loaded | 20 | 24 | 119 | 15 | 29 | 23 | 35 | 28 | 19 | 19 |
| Binaries Loaded | 11 | 6 | 23 | 2 | 10 | 6 | 9 | 14 | 12 | 7 |
| JARs Loaded | 10 | 41 | 51 | 16 | 88 | 76 | 182 | 144 | 69 | 9 |
| Directly Mapped Libraries Analysed | 11 | 15 | 19 | 8 | 15 | 18 | 15 | 18 | 15 | 7 |
