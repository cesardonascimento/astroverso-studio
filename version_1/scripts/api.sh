#!/bin/sh
# uso: sh scripts/api.sh METHOD /caminho ['{"json":1}']   — chama o worker com o token do .env
cd "$(dirname "$0")/.."
T=$(grep ^WORKER_TOKEN= .env | cut -d= -f2)
curl -sS -X "$1" "http://127.0.0.1:8090$2" -H "Authorization: Bearer $T" -H "Content-Type: application/json" ${3:+-d "$3"}
echo
