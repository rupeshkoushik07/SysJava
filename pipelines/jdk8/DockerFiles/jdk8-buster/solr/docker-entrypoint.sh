#!/usr/bin/env bash
set -euo pipefail

if [ "${1:-}" = "solr-foreground" ]; then
  shift
  exec /opt/solr/bin/solr -f \
    -s "${SOLR_HOME:-/var/solr/data}" \
    -p "${SOLR_PORT:-8983}" \
    "$@"
fi

exec "$@"
