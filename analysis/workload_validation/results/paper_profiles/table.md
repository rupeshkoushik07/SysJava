| Application | Workload ops per run | Base: ok / failed | Log: ok / failed | Enforce: ok / failed | Would be blocked (log mode) | Runs | Result |
|---|---:|---|---|---|---|---:|---|
| cassandra | 11 | 33 / 0 | 33 / 0 | 33 / 0 | none | 9 | PASS |
| elasticsearch | 250 | 750 / 0 | 750 / 0 | 750 / 0 | fchown | 9 | FAIL |
| groovy | 46 | 138 / 0 | 138 / 0 | 138 / 0 | none | 9 | PASS |
| jetty | 3,052 | 9,156 / 0 | 9,156 / 0 | 9,156 / 0 | fchdir, fchown | 9 | FAIL |
| jruby | 46 | 138 / 0 | 138 / 0 | 138 / 0 | none | 9 | PASS |
| orientdb | 1,808 | 5,424 / 0 | 5,424 / 0 | 5,424 / 0 | none | 9 | PASS |
| solr | 199 | 597 / 0 | 597 / 0 | 597 / 0 | times | 9 | FAIL |
| storm | 35 | 105 / 0 | 105 / 0 | 105 / 0 | fallocate, fchdir | 9 | FAIL |
| tomcat | 3,052 | 9,156 / 0 | 9,156 / 0 | 9,156 / 0 | fchdir | 9 | FAIL |
| zookeeper | 3,951 | 11,853 / 0 | 11,853 / 0 | 11,853 / 0 | none | 9 | PASS |
