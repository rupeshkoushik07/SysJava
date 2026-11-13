#!/usr/bin/env python3
"""trace/<app>/table_row.json -> table.md and policy_validation.tex (the paper's tab:policy-validation format:
missing / performed / permitted syscalls, new binaries / libraries)."""
import json, os
H = os.path.dirname(os.path.abspath(__file__))
ROWS = [("zookeeper", "Zookeeper 3.4.14", "zkCli + four-letter cmds"), ("tomcat", "Tomcat 7.0", "servlet/JSP GETs, POSTs, war deploy"),
        ("cassandra", "Cassandra 3.0.29", "cqlsh + cassandra-stress"), ("jetty", "Jetty 9.4.51", "static GETs, POSTs, war deploy"),
        ("storm", "Storm 2.4.0", "storm list + blobstore"), ("orientdb", "OrientDB 3.2.19", "REST CRUD, index, edges"),
        ("elasticsearch", "Elasticsearch 7.5.2", "bulk index, search, reindex"), ("solr", "Solr 8.7.0", "index, query, backup, unload"),
        ("groovy", "Groovy 4.0.0", "script: files, XML, zip, HTTP"), ("jruby", "JRuby 9.4.2.0", "script: files, JSON, zlib, TCP")]
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
