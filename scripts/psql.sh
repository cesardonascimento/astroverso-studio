#!/bin/sh
# Abre o psql num banco do studio. uso: STUDIO_DB=<banco> sh scripts/psql.sh [args do psql]  (padrão: cortes)
cd "$(dirname "$0")/.."
U=$(grep ^POSTGRES_USER= .env | cut -d= -f2)
exec podman exec -i astroverso-studio_postgres_1 psql -U "$U" -d "${STUDIO_DB:-cortes}" "$@"
