#!/bin/sh
# Importa e publica os fluxos de n8n/workflows no n8n. uso: sh scripts/n8n-deploy.sh
set -e
cd "$(dirname "$0")/.."
C=astroverso-studio_n8n_1
podman exec $C n8n import:workflow --separate --input=/workflows
for f in n8n/workflows/*.json; do
  id=$(grep -m1 '"id"' "$f" | sed 's/.*"id": *"\([^"]*\)".*/\1/')
  echo "[studio] publicando $id"
  podman exec $C n8n publish:workflow --id="$id"
done
podman restart $C >/dev/null
echo "[studio] n8n reiniciado"
