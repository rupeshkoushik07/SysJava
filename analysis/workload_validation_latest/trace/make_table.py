#!/usr/bin/env python3
"""trace/<app>/table_row.json -> table.md and policy_validation_rows.tex (tab:policy-validation format:
missing / performed / permitted syscalls, new binaries / libraries). Latest set; copy of the JDK 8 generator."""
import json, os
H = os.path.dirname(os.path.abspath(__file__))
ROWS = [("cassandra", "Cassandra 5.0.8", "cqlsh + cassandra-stress"), ("zookeeper", "Zookeeper 3.9.5", "zkCli + four-letter cmds"),
        ("tomcat", "Tomcat 11.0.22", "servlet/JSP GETs, POSTs, war deploy"), ("solr", "Solr 10.0.0", "collection, index, query, backup"),
        ("groovy", "Groovy 5.0.6", "script: files, XML, zip, HTTP"), ("orientdb", "OrientDB 3.2.53", "REST CRUD, index, edges"),
        ("jetty", "Jetty 12.1.10", "bare server: GETs, POSTs, keep-alive"), ("elasticsearch", "Elasticsearch 7.1.0", "bulk index, search, reindex"),
        ("storm", "Storm 2.8.8", "storm list + blobstore"), ("jruby", "JRuby 10.1.0.0", "script: files, JSON, zlib, TCP")]
md = ["| Container | Workload (ops) | Missing / performed / permitted | New binaries / libraries |", "|---|---|---|---|"]
tex = []
for app, name, wl in ROWS:
    r = json.load(open(f"{H}/{app}/table_row.json"))
    s = f"{len(r['missing'])} / {r['performed']} / {r['permitted']}"
    n = f"{len(r['new_binaries'])} / {len(r['new_libraries'])}"
    md.append(f"| {name} | {wl} ({r['ops_ok']:,}) | {s} | {n} |")
    tex.append(f"{name} & {wl} ({r['ops_ok']:,}) & {s} & {n} \\\\".replace(",", "{,}"))
open(f"{H}/table.md", "w").write("\n".join(md) + "\n")
open(f"{H}/policy_validation_rows.tex", "w").write("\n".join(tex) + "\n")
print("\n".join(md))
