#!/usr/bin/env bash
set -euo pipefail

if [ "${1:-}" = "elasticsearch" ]; then
  shift
  exec /opt/elasticsearch/bin/elasticsearch \
    -Ecluster.name="${CLUSTER_NAME:-docker-es-7.5.2}" \
    -Enode.name="${NODE_NAME:-es01}" \
    -Ediscovery.type=single-node \
    -Enetwork.host=0.0.0.0 \
    -Ehttp.port=9200 \
    -Epath.data=/usr/share/elasticsearch/data \
    -Epath.logs=/usr/share/elasticsearch/logs \
    "$@"
fi

exec "$@"
