#!/usr/bin/env bash
set -euo pipefail

if [ "${1:-}" = "groovy-hold" ]; then
  exec groovy -e 'println "Groovy " + GroovySystem.version + " on " + System.getProperty("java.version"); while (true) { Thread.sleep(3600000L) }'
fi

exec "$@"
