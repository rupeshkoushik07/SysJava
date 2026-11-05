| | Cassandra 5.0.8 | Zookeeper 3.9.5 | Tomcat 11.0.22 | Solr 10.0.0 | Groovy 5.0.6 | OrientDB 3.2.53 | Jetty 12.1.10 | Elasticsearch 7.1.0 | Storm 2.8.8 | JRuby 10.1.0.0 |
|---|---|---|---|---|---|---|---|---|---|---|
| of which JNA/FFI only | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 2 | 0 |
| Java Lib Syscalls | 133 | 133 | 116 | 138 | 120 | 88 | 121 | 111 | 140 | 107 |
| Container Binary Syscalls | 152 | 113 | 96 | 140 | 121 | 108 | 113 | 94 | 123 | 108 |
| Runtime Set, Additional | 22 | 29 | 36 | 25 | 33 | 36 | 32 | 35 | 23 | 34 |
| Library Fallback (delta) | 28 | 3 | 17 | 17 | 16 | 11 | 17 | 32 | 10 | 8 |
| Total Syscalls | 229 | 181 | 180 | 217 | 193 | 166 | 193 | 196 | 193 | 173 |
| check: total == union | ok | DIFF profile-only=[] union-only=['set_tid_address'] | ok | ok | ok | DIFF profile-only=[] union-only=['set_tid_address'] | ok | ok | ok | ok |
| Native methods (detector) | 1660 | 735 | 269 | 722 | 331 | 526 | 183 | 363 | 2802 | 460 |
| JVM RegisterNatives bindings | 847 | 860 | 469 | 640 | 416 | 317 | 469 | 339 | 1261 | 416 |
| App RegisterNatives bindings | 854 | 890 | 0 | 320 | 0 | 0 | 0 | 0 | 1698 | 0 |
| JNA hits | 40 | 38 | 384 | 3 | 31 | 3 | 2 | 23 | 51 | 40 |
| FFI/FFM hits | 7 | 9 | 384 | 3 | 2 | 3 | 2 | 2 | 51 | 2 |
| JNR-FFI hits | 3 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 40 |
| Libraries Observed | 437 | 80 | 42 | 132 | 92 | 131 | 54 | 231 | 260 | 55 |
| Executables Observed | 31 | 13 | 6 | 16 | 16 | 8 | 8 | 12 | 16 | 8 |
| JARs Observed | 95 | 43 | 38 | 146 | 73 | 79 | 7 | 153 | 94 | 3 |
| Libraries Analysed | 22 | 12 | 6 | 9 | 9 | 11 | 5 | 9 | 18 | 6 |
| Executables Analysed | 30 | 12 | 6 | 16 | 16 | 8 | 8 | 12 | 16 | 8 |
| Runs under profile | PASS | FAIL not_ready not_running probe_failed | PASS | PASS | PASS | FAIL not_ready not_running probe_failed | PASS | PASS | PASS | PASS |
