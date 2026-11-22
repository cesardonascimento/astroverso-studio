#!/bin/sh
# Importa e publica os workflows de n8n/workflows no container do n8n.
# uso (no WSL): sh scripts/n8n-deploy.sh
set -e
C=astroverso-studio_n8n_1
podman exec $C n8n import:workflow --separate --input=/workflows
cd "$(dirname "$0")/.."
for f in n8n/workflows/*.json; do
  id=$(grep -m1 '"id"' "$f" | sed 's/.*"id": *"\([^"]*\)".*/\1/')
  echo "publicando $id"
  podman exec $C n8n publish:workflow --id="$id"
done
podman restart $C >/dev/null
echo "n8n reiniciado"
