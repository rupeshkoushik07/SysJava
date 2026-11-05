#!/usr/bin/env python3
"""Extend the artifact's copy of the JDK 8 pipeline with the five official
JDK 8 images of Table tab:results (zookeeper:3.4.14, tomcat:7.0,
cassandra:3.0.29, orientdb:3.2.19, jruby:9.4.2.0).

    add_jdk8_official_targets.py <2_swat4j_vs_sysjava/scripts>

The pipeline is unchanged; only the per-image settings are added (image, docker
run arguments, ready log line), plus one readiness rule for images that print
no ready line (JRuby's irb): the JVM has been running for 30 s. The same rule
is used by the latest-versions pipeline. Ready lines are the ones the SWAT4J
dynamic run uses for the same images (swat4j/dynamic_swat4j.sh).
Applied by tools/build_artifact.sh; fails if an anchor is missing.
"""
import os
import sys

D = sys.argv[1]


def patch(name, edits):
    p = os.path.join(D, name)
    s = open(p).read()
    for old, new in edits:
        if new in s:
            continue
        if s.count(old) != 1:
            sys.exit(f"{name}: anchor not found exactly once: {old[:60]!r}")
        s = s.replace(old, new)
    open(p, "w").write(s)


CASES = '''    zookeeper_3.4.14)
        IMAGE=zookeeper:3.4.14; RUN_ARGS=(); CMD=(); MARKER="binding to port" ;;
    tomcat_7.0)
        IMAGE=tomcat:7.0; RUN_ARGS=(); CMD=(); MARKER="Server startup in" ;;
    cassandra_3.0.29)
        IMAGE=cassandra:3.0.29; RUN_ARGS=(-e MAX_HEAP_SIZE=1G -e HEAP_NEWSIZE=256M); CMD=()
        MARKER="Starting listening for CQL clients" ;;
    orientdb_3.2.19)
        IMAGE=orientdb:3.2.19; RUN_ARGS=(-e ORIENTDB_ROOT_PASSWORD=root); CMD=(); MARKER="OrientDB Studio available" ;;
    jruby_9.4.2.0)
        # irb needs a terminal and prints nothing: ready = JVM up for 30 s.
        IMAGE=jruby:9.4.2.0; RUN_ARGS=(-it); CMD=(); MARKER="" ;;
'''

JVM_UP = '''elif [ "${T#storm}" = "$T" ]; then
            started="$(docker inspect -f '{{.State.StartedAt}}' "$CNAME")"
            [ $(( $(date +%s) - $(date -d "$started" +%s) )) -ge 30 ] \\
                && docker top "$CNAME" -eo pid,args | grep -q java && return 0
        else'''

patch("run_jdk8_target.sh", [
    ('    *) echo "unknown target $T" >&2; exit 1 ;;', CASES + '    *) echo "unknown target $T" >&2; exit 1 ;;'),
    ('#           jetty_9.4.51-jdk8-buster\n',
     '#           jetty_9.4.51-jdk8-buster\n'
     '#           official JDK 8 images: zookeeper_3.4.14 | tomcat_7.0 | cassandra_3.0.29 |\n'
     '#           orientdb_3.2.19 | jruby_9.4.2.0\n'),
    ('''            docker logs "$CNAME" 2>&1 | grep -q -- "$MARKER" && return 0
        else''', '''            docker logs "$CNAME" 2>&1 | grep -q -- "$MARKER" && return 0
        ''' + JVM_UP),
])

patch("verify_seccomp_profile.sh", [
    ('''        docker logs "$1" 2>&1 | grep -q -- "$MARKER"
    else''', '''        docker logs "$1" 2>&1 | grep -q -- "$MARKER"
    elif [ "${T#storm}" = "$T" ]; then  # no ready line: JVM up for 30 s
        local started; started="$(docker inspect -f '{{.State.StartedAt}}' "$1")"
        [ $(( $(date +%s) - $(date -d "$started" +%s) )) -ge 30 ] && docker top "$1" -eo pid,args | grep -q java
    else'''),
])
print("added zookeeper_3.4.14 tomcat_7.0 cassandra_3.0.29 orientdb_3.2.19 jruby_9.4.2.0 to", D)
