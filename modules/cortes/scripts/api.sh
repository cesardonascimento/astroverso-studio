#!/bin/sh
# Chama a API do módulo cortes. uso: sh modules/cortes/scripts/api.sh METHOD /caminho ['{"json":1}' | @arquivo]
cd "$(dirname "$0")/../../.."
T=$(grep ^WORKER_TOKEN= .env | cut -d= -f2)
curl -sS -X "$1" "http://127.0.0.1:8091$2" -H "Authorization: Bearer $T" -H "Content-Type: application/json" ${3:+-d "$3"}
echo
