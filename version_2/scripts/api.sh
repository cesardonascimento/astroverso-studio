#!/bin/sh
# uso: sh scripts/api.sh METHOD /caminho ['{"json":1}']
cd "$(dirname "$0")/.."
T=$(grep ^WORKER_TOKEN= .env | cut -d= -f2)
curl -sS -X "$1" "http://127.0.0.1:8091$2" -H "Authorization: Bearer $T" -H "Content-Type: application/json" ${3:+-d "$3"}
echo
