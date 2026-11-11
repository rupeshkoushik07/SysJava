| Application | Workload ops per run | Base: ok / failed | Log: ok / failed | Enforce: ok / failed | Would be blocked (log mode) | Runs | Result |
|---|---:|---|---|---|---|---:|---|
| cassandra | 11 | 33 / 0 | 33 / 0 | 33 / 0 | openat2 | 9 | FAIL |
| elasticsearch | 250 | 750 / 0 | 750 / 0 | 750 / 0 | close_range, faccessat2, openat2 | 9 | FAIL |
| groovy | 46 | 138 / 0 | 138 / 0 | 138 / 0 | openat2 | 9 | FAIL |
| jetty | 3,075 | 9,225 / 0 | 9,225 / 0 | 9,225 / 0 | openat2 | 9 | FAIL |
| jruby | 46 | 138 / 0 | 138 / 0 | 138 / 0 | flock, openat2 | 9 | FAIL |
| orientdb | 1,808 | 5,424 / 0 | 5,424 / 0 | 5,424 / 0 | close_range, openat2 | 9 | FAIL |
| solr | 194 | 582 / 0 | 582 / 0 | 582 / 0 | openat2 | 9 | FAIL |
| storm | 35 | 105 / 0 | 105 / 0 | 105 / 0 | openat2, sync_file_range | 9 | FAIL |
| tomcat | 3,052 | 9,156 / 0 | 9,156 / 0 | 8,406 / 750 | copy_file_range, flock, openat2 | 9 | FAIL |
| zookeeper | 3,951 | 11,853 / 0 | 11,853 / 0 | 11,853 / 0 | openat2 | 9 | FAIL |
