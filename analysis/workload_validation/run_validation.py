#!/usr/bin/env python3
"""Workload validation of the generated seccomp profiles (JDK 8 set).

For each application and repetition the same container is run three times with the same workload:
  base     Docker's default seccomp (what the pipeline's baseline uses)
  log      the generated profile with defaultAction SCMP_ACT_LOG: nothing is blocked, and every syscall
           the profile would deny is written to the audit log (auditd: /var/log/audit/audit.log, type=SECCOMP,
           code=0x7ffc0000), attributed to the container by its host PIDs
  enforce  the generated profile as published
The workload is driven from the host (or, for Cassandra, from an unconfined client container), so no
tool process runs inside the confined container. Every workload request is counted ok / failed.
PASS for an application: in every repetition, the enforce run completes the same operations as base
with no failures, and the log run records no syscall outside the profile.

Usage: run_validation.py <app> [<app> ...] [--reps N] [--modes base,log,enforce]
  apps: solr cassandra elasticsearch tomcat zookeeper jetty orientdb storm groovy jruby
  env:  WLV_PROFILE_DIR   folder of <t>.json profiles (default: the pipeline results, Final_results_JDK8)
        WLV_RESULTS       results folder name (default: results)
Output: $WLV_RESULTS/<app>/<mode>_<rep>.json, .container.log, .audit.log (log mode), $WLV_RESULTS/summary.tsv
"""
import argparse, json, os, re, shutil, subprocess, sys, time, urllib.parse, urllib.request, urllib.error

RES = os.environ.get("WLV_RESULTS", "results")   # results folder (relative to this script)
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.expanduser("~/Tutorial/EchoTrace/Final_results_JDK8")
APPS = {
    "solr": dict(t="solr_8.7.0-jdk8-buster", image="solr:8.7.0-jdk8-buster", args=[], port=8983,
                 ready="/solr/admin/info/system"),
    "cassandra": dict(t="cassandra_3.0.29-jdk8-buster", image="cassandra:3.0.29-jdk8-buster",
                      args=["-e", "MAX_HEAP_SIZE=1G", "-e", "HEAP_NEWSIZE=256M"], port=9042, ready=None),
    "elasticsearch": dict(t="elasticsearch_7.5.2-jdk8-buster", image="elasticsearch:7.5.2-jdk8-buster",
                          args=["-e", "ES_JAVA_OPTS=-Xms1g -Xmx1g"],
                          port=9200, ready="/_cluster/health"),
    "tomcat": dict(t="tomcat_7.0-jdk8-buster", image="tomcat:7.0-jdk8-buster", args=[], port=8080,
                   ready="/examples/"),
    "zookeeper": dict(t="zookeeper_3.4.14-jdk8-buster", image="zookeeper:3.4.14-jdk8-buster", args=[], port=2181, ready=None),
    "jetty": dict(t="jetty_9.4.51-jdk8-buster", image="jetty:9.4.51-jdk8-buster", args=[], port=8080, ready="/wl/tomcat.css"),
    "orientdb": dict(t="orientdb_3.2.19-jdk8-buster", image="orientdb:3.2.19-jdk8-buster",
                     args=["-e", "ORIENTDB_ROOT_PASSWORD=root"], port=2480, ready="/listDatabases"),
    "storm": dict(t="storm_2.4.0-jdk8-buster", image="storm:2.4.0-jdk8-buster",
                  args=["--network", "et-jdk8-net", "--hostname", "nimbus", "--network-alias", "nimbus"], cmd=["nimbus"],
                  port=6627, ready=None),
    "groovy": dict(t="groovy_4.0.0-jdk8-buster", image="groovy:4.0.0-jdk8-buster", args=[], batch=["groovy", "/wl/workload.groovy"]),
    "jruby": dict(t="jruby_9.4.2.0-jdk8-buster", image="jruby:9.4.2.0-jdk8-buster", args=[], batch=["jruby", "/wl/workload.rb"]),
}


def sh(cmd, check=False, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, check=check, **kw)


def ip_of(name):
    return sh(["docker", "inspect", "-f", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", name]).stdout.strip()


def http(method, url, body=None, ctype="application/json", timeout=60, headers=None):
    data = body.encode() if isinstance(body, str) else body
    h = dict(headers or {})
    if data:
        h["Content-Type"] = ctype
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return 0, str(e).encode()


class Count:
    def __init__(self):
        self.ok, self.fail, self.errors = 0, 0, {}

    def add(self, what, good, detail=""):
        if good:
            self.ok += 1
        else:
            self.fail += 1
            self.errors.setdefault(what, detail[:200])


# ------------------------------------------------------------------ workloads (host side)
def wl_solr(ip, c, data):
    b = f"http://{ip}:8983/solr"
    s, _ = http("GET", f"{b}/admin/cores?action=CREATE&name=wl&configSet=_default&wt=json")
    c.add("create_core", s == 200, str(s))
    docs = sorted(f for f in os.listdir(data["solr_docs"]) if f.endswith(".xml"))
    for rnd in range(5):                                      # index the example documents 5 times
        for f in docs:
            s, out = http("POST", f"{b}/wl/update", open(os.path.join(data["solr_docs"], f), "rb").read(), "text/xml")
            c.add("post " + f, s == 200, str(s) + out.decode(errors="replace")[:100])
        bulk = json.dumps([{"id": f"gen-{rnd}-{i}", "name_s": f"item {i}", "price_f": i * 1.5, "cat_ss": ["a", "b"]}
                           for i in range(2000)])
        s, _ = http("POST", f"{b}/wl/update?commit=true", bulk)
        c.add("bulk json", s == 200, str(s))
    for q in ["q=*:*", "q=name:ipod", "q=*:*&facet=true&facet.field=cat", "q=price_f:[10 TO 100]&sort=price_f desc",
              "q=*:*&rows=500", "q=name_s:item*&fl=id"] * 20:
        s, _ = http("GET", f"{b}/wl/select?" + urllib.parse.urlencode(dict(x.split("=", 1) for x in q.split("&"))) + "&wt=json")
        c.add("query", s == 200, str(s))
    s, _ = http("POST", f"{b}/wl/update?optimize=true", "{}")
    c.add("optimize", s == 200, str(s))
    s, _ = http("GET", f"{b}/wl/replication?command=backup&name=wlbak&wt=json")
    c.add("backup", s == 200, str(s))
    time.sleep(5)
    s, _ = http("GET", f"{b}/admin/cores?action=UNLOAD&core=wl&deleteIndex=true&deleteDataDir=true&deleteInstanceDir=true&wt=json")
    c.add("unload+delete core", s == 200, str(s))


def wl_elasticsearch(ip, c, data):
    b = f"http://{ip}:9200"
    for idx in ("wl1", "wl2"):
        s, _ = http("PUT", f"{b}/{idx}", json.dumps({"settings": {"number_of_shards": 2, "number_of_replicas": 0}}))
        c.add("create index", s == 200, str(s))
        for batch in range(20):                                 # 20 x 1000 docs
            lines = []
            for i in range(1000):
                n = batch * 1000 + i
                lines.append(json.dumps({"index": {"_id": str(n)}}))
                lines.append(json.dumps({"name": f"place {n}", "pop": n % 9973, "country": f"c{n % 50}",
                                         "loc": {"lat": (n % 180) - 90, "lon": (n % 360) - 180}}))
            s, out = http("POST", f"{b}/{idx}/_bulk", "\n".join(lines) + "\n", "application/x-ndjson")
            c.add("bulk", s == 200 and b'"errors":false' in out, str(s))
        http("POST", f"{b}/{idx}/_refresh")
        for body in [{"query": {"match": {"name": "place"}}}, {"query": {"range": {"pop": {"gte": 100, "lte": 500}}}},
                     {"size": 0, "aggs": {"c": {"terms": {"field": "country.keyword"}}}},
                     {"query": {"term": {"country.keyword": "c7"}}, "sort": [{"pop": "desc"}]}] * 25:
            s, _ = http("POST", f"{b}/{idx}/_search", json.dumps(body))
            c.add("search", s == 200, str(s))
        s, _ = http("POST", f"{b}/{idx}/_forcemerge?max_num_segments=1")
        c.add("forcemerge", s == 200, str(s))
        s, _ = http("POST", f"{b}/{idx}/_update_by_query?conflicts=proceed", json.dumps({"script": {"source": "ctx._source.pop++"}}))
        c.add("update_by_query", s == 200, str(s))
    s, _ = http("POST", f"{b}/_reindex", json.dumps({"source": {"index": "wl1"}, "dest": {"index": "wl3"}}))
    c.add("reindex", s == 200, str(s))
    for idx in ("wl1", "wl2", "wl3"):
        s, _ = http("DELETE", f"{b}/{idx}")
        c.add("delete index", s == 200, str(s))


def wl_tomcat(ip, c, data):
    b = f"http://{ip}:8080"
    pages = ["/examples/servlets/servlet/HelloWorldExample", "/examples/servlets/servlet/RequestInfoExample",
             "/examples/servlets/servlet/RequestHeaderExample", "/examples/servlets/servlet/CookieExample",
             "/examples/jsp/jsp2/el/basic-arithmetic.jsp", "/examples/jsp/jsp2/simpletag/hello.jsp",
             "/examples/jsp/dates/date.jsp", "/examples/jsp/num/numguess.jsp", "/examples/jsp/sessions/carts.jsp?item=x&submit=add",
             "/docs/", "/docs/config/http.html", "/examples/index.html"]

    def one(p):
        s, _ = http("GET", b + p, timeout=30)
        return p, s

    with ThreadPoolExecutor(16) as ex:                         # 3,000 requests, 16 at a time
        for p, s in ex.map(one, pages * 250):
            c.add("GET " + p, s == 200, str(s))
    for i in range(50):
        s, _ = http("POST", b + "/examples/servlets/servlet/RequestParamExample", f"firstname=a{i}&lastname=b",
                    "application/x-www-form-urlencoded")
        c.add("POST form", s == 200, str(s))
    # hot deployment: drop a war into the mounted webapps dir, use it, remove it (undeploy deletes the dir)
    shutil.copy(data["war"], os.path.join(data["webapps"], "wl.war"))
    for _ in range(60):
        s, _ = http("GET", b + "/wl/")
        if s == 200:
            break
        time.sleep(2)
    c.add("deploy war", s == 200, str(s))
    os.remove(os.path.join(data["webapps"], "wl.war"))
    for _ in range(60):
        s, _ = http("GET", b + "/wl/")
        if s == 404:
            break
        time.sleep(2)
    c.add("undeploy war", s == 404, str(s))


def wl_cassandra(ip, c, data):
    img = APPS["cassandra"]["image"]
    run = lambda *cmd: sh(["docker", "run", "--rm", "--entrypoint", cmd[0], img, *cmd[1:]], timeout=1800)
    cql = lambda q: run("cqlsh", ip, "-e", q)
    for q in ["CREATE KEYSPACE wl WITH replication = {'class':'SimpleStrategy','replication_factor':1};",
              "CREATE TABLE wl.t (id int PRIMARY KEY, v text, n int);",
              "CREATE INDEX ON wl.t (n);",
              "BEGIN BATCH " + " ".join(f"INSERT INTO wl.t (id,v,n) VALUES ({i},'v{i}',{i % 10});" for i in range(200)) + " APPLY BATCH;",
              "SELECT count(*) FROM wl.t;", "SELECT * FROM wl.t WHERE n = 3;", "TRUNCATE wl.t;",
              "DROP KEYSPACE wl;"]:
        r = cql(q)
        c.add("cql " + q[:30], r.returncode == 0, r.stderr[-200:])
    for op in ("write", "read", "mixed ratio(write=1,read=3)"):
        r = run("/opt/cassandra/tools/bin/cassandra-stress", *op.split(), "n=60000", "-rate", "threads=16",
                "-node", ip, "-mode", "native", "cql3")
        good = r.returncode == 0 and "END" in r.stdout and not re.search(r"Error|Exception", r.stdout[-3000:])
        c.add("stress " + op.split()[0], good, (r.stdout + r.stderr)[-300:])


def wl_zookeeper(ip, c, data):
    import socket
    def four(cmd):
        with socket.create_connection((ip, 2181), timeout=10) as so:
            so.sendall(cmd.encode()); so.shutdown(socket.SHUT_WR)
            return b"".join(iter(lambda: so.recv(4096), b"")).decode(errors="replace")
    for cmd in ("ruok", "stat", "srvr", "conf", "cons", "envi", "mntr", "wchs", "dump") * 3:
        try:
            c.add("4lw " + cmd, len(four(cmd)) > 0, "")
        except Exception as e:
            c.add("4lw " + cmd, False, repr(e))
    cmds = ["create /wl root"] + [f"create /wl/n{i} v{i}" for i in range(400)] + \
           [f"set /wl/n{i} w{i}" for i in range(400)] + [f"get /wl/n{i}" for i in range(0, 400, 4)] + \
           ["ls /wl", "stat /wl", "sync /wl", "create -s /wl/seq x", "create -e /wl/eph x"] + \
           [f"delete /wl/n{i}" for i in range(400)] + ["rmr /wl", "quit"]
    for rnd in range(3):
        r = subprocess.run(["docker", "run", "--rm", "-i", "--entrypoint", "/zookeeper-3.4.14/bin/zkCli.sh",
                            APPS["zookeeper"]["image"], "-server", f"{ip}:2181"],
                           input="\n".join(cmds) + "\n", capture_output=True, text=True, timeout=600)
        bad = re.findall(r"(Exception|KeeperErrorCode[^\n]*)", r.stdout + r.stderr)
        c.ok += len(cmds) - len(bad)
        if bad or r.returncode != 0:
            c.add(f"zkCli round {rnd}", False, (bad or [r.stderr[-200:]])[0])


def wl_jetty(ip, c, data):
    b = f"http://{ip}:8080"
    files = ["/wl/bg-nav.png", "/wl/tomcat.css", "/wl/RELEASE-NOTES.txt", "/wl/tomcat.gif", "/wl/asf-logo-wide.svg", "/wl/favicon.ico"]
    def one(p):
        s, _ = http("GET", b + p, timeout=30)
        return p, s
    with ThreadPoolExecutor(16) as ex:
        for p, s in ex.map(one, files * 500):
            c.add("GET " + p, s == 200, str(s))
    for i in range(50):
        s, _ = http("POST", b + "/wl/RELEASE-NOTES.txt", f"a={i}", "application/x-www-form-urlencoded")
        c.add("POST", s in (200, 405), str(s))
    shutil.copy(data["war"], os.path.join(data["webapps"], "wl2.war"))
    for _ in range(60):
        s, _ = http("GET", b + "/wl2/tomcat.css")
        if s == 200:
            break
        time.sleep(2)
    c.add("hot deploy", s == 200, str(s))
    os.remove(os.path.join(data["webapps"], "wl2.war"))
    for _ in range(60):
        s, _ = http("GET", b + "/wl2/tomcat.css")
        if s == 404:
            break
        time.sleep(2)
    c.add("undeploy", s == 404, str(s))


def wl_orientdb(ip, c, data):
    import base64
    b, H = f"http://{ip}:2480", {"Authorization": "Basic " + base64.b64encode(b"root:root").decode()}
    s, _ = http("POST", f"{b}/database/wl/plocal", "", headers=H)
    c.add("create db", s == 200, str(s))
    sql = lambda q: http("POST", f"{b}/command/wl/sql", json.dumps({"command": q}), headers=H)
    for q in ["CREATE CLASS Person EXTENDS V", "CREATE PROPERTY Person.name STRING", "CREATE PROPERTY Person.age INTEGER",
              "CREATE INDEX Person.name NOTUNIQUE", "CREATE CLASS Knows EXTENDS E"]:
        s, out = sql(q)
        c.add(q[:20], s == 200, str(s) + out.decode(errors="replace")[:100])
    for i in range(1500):
        s, _ = sql(f"INSERT INTO Person SET name = 'p{i}', age = {i % 90}")
        c.add("insert", s == 200, str(s))
    for i in range(0, 1400, 7):
        s, _ = sql(f"CREATE EDGE Knows FROM (SELECT FROM Person WHERE name='p{i}') TO (SELECT FROM Person WHERE name='p{i + 1}')")
        c.add("edge", s == 200, str(s))
    for q in ["SELECT count(*) FROM Person", "SELECT FROM Person WHERE age > 50 LIMIT 100",
              "SELECT FROM Person WHERE name = 'p42'", "SELECT expand(out('Knows')) FROM Person WHERE name = 'p7'"] * 25:
        s, _ = http("GET", f"{b}/query/wl/sql/" + urllib.parse.quote(q), headers=H)
        c.add("query", s == 200, str(s))
    s, _ = sql("UPDATE Person SET age = age + 1 WHERE age < 10")
    c.add("update", s == 200, str(s))
    s, _ = http("DELETE", f"{b}/database/wl", headers=H)
    c.add("drop db", s in (200, 204), str(s))


def wl_storm(ip, c, data):
    img = APPS["storm"]["image"]
    conf = ["-c", 'nimbus.seeds=["nimbus"]', "-c", 'storm.zookeeper.servers=["zookeeper"]']
    def storm(*a, inp=None):
        return subprocess.run(["docker", "run", "--rm", "-i", "--network", "et-jdk8-net", "--entrypoint", "storm", img,
                               *a, *conf], input=inp, capture_output=True, text=True, timeout=600)
    for i in range(10):
        r = storm("list")
        c.add("list", r.returncode == 0, r.stderr[-200:])
    for i in range(5):
        k = f"wlblob{i}"
        r = storm("blobstore", "create", k, "-f", "/opt/storm/bin/storm.py", "-a", "o::rwa")
        c.add("blob create", r.returncode == 0, (r.stdout + r.stderr)[-200:])
        r = storm("blobstore", "list", k)
        c.add("blob list", r.returncode == 0 and k in r.stdout, (r.stdout + r.stderr)[-200:])
        r = storm("blobstore", "cat", k)
        c.add("blob cat", r.returncode == 0 and len(r.stdout) > 100, (r.stdout + r.stderr)[-200:])
        r = storm("blobstore", "update", k, "-f", "/opt/storm/bin/storm")
        c.add("blob update", r.returncode == 0, (r.stdout + r.stderr)[-200:])
        r = storm("blobstore", "delete", k)
        c.add("blob delete", r.returncode == 0, (r.stdout + r.stderr)[-200:])


# ------------------------------------------------------------------ one run
def wait_ready(name, app):
    ip = ip_of(name)
    for _ in range(120):
        if sh(["docker", "inspect", "-f", "{{.State.Running}}", name]).stdout.strip() != "true":
            return None
        lg = sh(["docker", "logs", name])
        lg = lg.stdout + lg.stderr
        if app == "cassandra":
            if "Starting listening for CQL clients" in lg:
                return ip
        elif app == "zookeeper":
            if "binding to port" in lg:
                time.sleep(3)
                return ip
        elif app == "storm":
            # nimbus logs to /opt/storm/logs/nimbus.log, not stdout: ready = Thrift port accepting
            import socket
            try:
                socket.create_connection((ip, APPS[app]["port"]), timeout=3).close()
                time.sleep(10)
                return ip
            except OSError:
                pass
        else:
            import base64
            s, _ = http("GET", f"http://{ip}:{APPS[app]['port']}{APPS[app]['ready']}", timeout=5,
                        headers={"Authorization": "Basic " + base64.b64encode(b"root:root").decode()})
            if s == 200:
                return ip
        time.sleep(3)
    return None


def profile_path(app):
    """The profile the paper reports. Storm: 172, without `sync` from false FFM hits (_tables/REPRODUCE.md)."""
    t = APPS[app]["t"]
    d = os.environ.get("WLV_PROFILE_DIR") or (None if os.path.isdir(R) else f"{HERE}/profiles/fixed")
    if d:                                             # a folder of <t>.json profiles (the artifact's profiles/<set>/)
        return os.path.join(d, f"{t}.json")
    if app == "storm":
        return os.environ.get("WLV_STORM_PROFILE", f"{R}/_tables/storm_no_false_ffm_rta/{t}.json")
    return f"{R}/{t}/Binary_Analysis/syscalls_output_{t}/{t}.json"


def log_profile(app):
    t = APPS[app]["t"]
    p = json.load(open(profile_path(app)))
    p["defaultAction"] = "SCMP_ACT_LOG"
    p.pop("defaultErrnoRet", None)
    out = f"{HERE}/profiles/{t}.log.json"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(p, open(out, "w"), indent=1)
    return out


def denials(since, pids):
    """SCMP_ACT_LOG records (type=SECCOMP, code=0x7ffc0000) since <since> (epoch seconds), split into this
    container's (process seen in the container) and unattributed ones (other containers in log mode at
    the same time). auditd is running on this host, so the records are in /var/log/audit/audit.log (and
    audit.log.1 after a rotation), not in the kernel log."""
    out = sh(["sudo", "-n", "sh", "-c", "cat /var/log/audit/audit.log.1 /var/log/audit/audit.log 2>/dev/null"]).stdout
    mine, other, raw = {}, {}, []
    for l in out.splitlines():
        if "type=SECCOMP" not in l or "code=0x7ffc0000" not in l:
            continue
        if float(re.search(r"audit\((\d+\.\d+):", l).group(1)) < since:
            continue
        sc = re.search(r"syscall=(\d+)", l).group(1)
        exe = (re.search(r'exe="([^"]*)"', l) or re.search(r"exe=(\S+)", l)).group(1)
        pid = re.search(r" pid=(\d+)", l).group(1)
        name = sh(["ausyscall", "x86_64", sc]).stdout.strip() or sc
        (mine if pid in pids else other).setdefault(name, set()).add(exe)
        raw.append(("" if pid in pids else "# not this container: ") + l)
    f = lambda d: {k: sorted(v) for k, v in d.items()}
    return f(mine), f(other), raw


def one_run(app, mode, rep, data):
    a, t = APPS[app], APPS[app]["t"]
    name = f"wlv-{app}-{mode}-{rep}"
    sh(["docker", "rm", "-f", name])
    sec = []
    if mode == "enforce":
        sec = ["--security-opt", f"seccomp={profile_path(app)}"]
    elif mode == "log":
        sec = ["--security-opt", f"seccomp={log_profile(app)}"]
    extra = []
    if app == "tomcat":
        data["webapps"] = f"{HERE}/work/tomcat_webapps_{mode}_{rep}"
        if os.path.isdir(data["webapps"]):            # Tomcat (root in the container) leaves root-owned files
            sh(["sudo", "-n", "rm", "-rf", "--", data["webapps"]])
        shutil.copytree(data["tomcat_dist"], data["webapps"])
        os.chmod(data["webapps"], 0o777)
        extra = ["-v", f"{data['webapps']}:/usr/local/tomcat/webapps"]
    if app == "jetty":
        data["webapps"] = f"{HERE}/work/jetty_webapps_{mode}_{rep}"
        if os.path.isdir(data["webapps"]):
            sh(["sudo", "-n", "rm", "-rf", "--", data["webapps"]])
        os.makedirs(data["webapps"])
        os.chmod(data["webapps"], 0o777)
        shutil.copy(data["war"], f"{data['webapps']}/wl.war")
        extra = ["-v", f"{data['webapps']}:/var/lib/jetty/webapps"]
    if a.get("batch"):
        extra = ["-v", f"{HERE}/scripts:/wl:ro"]
    if app == "storm":                                # nimbus needs ZooKeeper (as in the pipeline's stage 10)
        if sh(["docker", "network", "inspect", "et-jdk8-net"]).returncode:
            sh(["docker", "network", "create", "et-jdk8-net"])
        if sh(["docker", "inspect", "et-jdk8-zookeeper"]).returncode:
            sh(["docker", "run", "-d", "--name", "et-jdk8-zookeeper", "--network", "et-jdk8-net",
                "--network-alias", "zookeeper", "zookeeper:3.7"])
            time.sleep(10)
    since = time.time()
    t0 = time.time()
    r = sh(["docker", "run", "-d", "--name", name, *sec, *extra, *a["args"], a["image"], *a.get("batch", a.get("cmd", []))])
    pids, stop = set(), [False]

    def poll():                                       # host PIDs of every process in the container
        while not stop[0]:
            out = sh(["docker", "top", name, "-eo", "pid"]).stdout.split()[1:]
            pids.update(x for x in out if x.isdigit())
            time.sleep(1)
    import threading
    th = threading.Thread(target=poll, daemon=True)
    th.start()
    res = dict(app=app, mode=mode, rep=rep, started=r.returncode == 0)
    if a.get("batch"):                                # the workload is the container's own program
        ex = sh(["docker", "wait", name]).stdout.strip()
        lg = sh(["docker", "logs", name])
        m = re.search(r"OPS ok=(\d+) fail=(\d+)", lg.stdout)
        ip = None
        res["exit_code"] = ex
    else:
        ip = wait_ready(name, app) if r.returncode == 0 else None
    res["ready"] = ip is not None or bool(a.get("batch"))
    res["ready_after_s"] = round(time.time() - t0)
    c = Count()
    if ip:
        if app == "cassandra":
            time.sleep(10)
        try:
            globals()["wl_" + app](ip, c, data)
        except Exception as e:
            c.add("workload exception", False, repr(e))
    if a.get("batch"):
        if m:
            c.ok, c.fail = int(m.group(1)), int(m.group(2))
        else:
            c.add("no OPS line", False, (lg.stdout + lg.stderr)[-300:])
        if ex != "0":
            c.add("exit code", False, ex)
        c.errors.update({"stderr": lg.stderr[-300:]} if c.fail else {})
    res.update(ops_ok=c.ok, ops_failed=c.fail, errors=c.errors, workload_s=round(time.time() - t0) - res["ready_after_s"])
    res["running_after"] = sh(["docker", "inspect", "-f", "{{.State.Running}}", name]).stdout.strip() == "true"
    logs = sh(["docker", "logs", name])
    os.makedirs(f"{HERE}/{RES}/{app}", exist_ok=True)
    open(f"{HERE}/{RES}/{app}/{mode}_{rep}.container.log", "w").write(logs.stdout + logs.stderr)
    time.sleep(2)
    stop[0] = True
    res["pids_seen"] = len(pids)
    res["would_be_denied"], res["unattributed_log_records"], raw = denials(since, pids) if mode == "log" else ({}, {}, [])
    if mode == "log":                                 # the raw audit records behind would_be_denied
        open(f"{HERE}/{RES}/{app}/{mode}_{rep}.audit.log", "w").write("".join(l + "\n" for l in raw))
    sh(["docker", "rm", "-f", name])
    json.dump(res, open(f"{HERE}/{RES}/{app}/{mode}_{rep}.json", "w"), indent=1)
    print(f"{app} {mode} rep{rep}: ready={res['ready']} ok={c.ok} failed={c.fail} running={res['running_after']} "
          f"denied={res['would_be_denied']}", flush=True)
    return res


def prepare():
    data = {}
    w = f"{HERE}/work"
    os.makedirs(w, exist_ok=True)
    if not os.path.isdir(f"{w}/solr_docs"):
        sh(["docker", "create", "--name", "wlv-cp", "solr:8.7.0-jdk8-buster"])
        sh(["docker", "cp", "wlv-cp:/opt/solr/example/exampledocs", f"{w}/solr_docs"])
        sh(["docker", "rm", "wlv-cp"])
    if not os.path.isdir(f"{w}/tomcat_dist"):
        sh(["docker", "create", "--name", "wlv-cp", "tomcat:7.0-jdk8-buster"])
        sh(["docker", "cp", "wlv-cp:/usr/local/tomcat/webapps.dist", f"{w}/tomcat_dist"])
        sh(["docker", "rm", "wlv-cp"])
        for d in ("manager", "host-manager"):               # admin apps need credentials; not part of the workload
            shutil.rmtree(f"{w}/tomcat_dist/{d}", ignore_errors=True)
        sh(["chmod", "-R", "a+rwX", f"{w}/tomcat_dist"])
    if not os.path.exists(f"{w}/wl.war"):
        shutil.make_archive(f"{w}/wl", "zip", f"{w}/tomcat_dist/ROOT")
        os.rename(f"{w}/wl.zip", f"{w}/wl.war")
    data.update(solr_docs=f"{w}/solr_docs", tomcat_dist=f"{w}/tomcat_dist", war=f"{w}/wl.war")
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("apps", nargs="+")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--modes", default="base,log,enforce")
    a = ap.parse_args()
    data = prepare()
    for app in a.apps:
        for rep in range(1, a.reps + 1):
            for mode in a.modes.split(","):
                one_run(app, mode, rep, data)
    summarize()


def summarize():
    rows = ["app\trep\tmode\tready\tops_ok\tops_failed\trunning_after\twould_be_denied"]
    for app in sorted(os.listdir(f"{HERE}/{RES}")):
        if not os.path.isdir(f"{HERE}/{RES}/{app}"):
            continue
        for f in sorted(os.listdir(f"{HERE}/{RES}/{app}")):
            if f.endswith(".json"):
                r = json.load(open(f"{HERE}/{RES}/{app}/{f}"))
                rows.append(f"{app}\t{r['rep']}\t{r['mode']}\t{r['ready']}\t{r['ops_ok']}\t{r['ops_failed']}\t"
                            f"{r['running_after']}\t{json.dumps(r['would_be_denied'])}")
    open(f"{HERE}/{RES}/summary.tsv", "w").write("\n".join(rows) + "\n")


if __name__ == "__main__":
    main()
