#!/bin/sh
# uso: sh data/media/psql.sh [args do psql]
cd "$(dirname "$0")/.."
U=$(grep ^POSTGRES_USER= .env | cut -d= -f2); D=$(grep ^POSTGRES_DB= .env | cut -d= -f2)
exec podman exec -i astroverso-studio-v1_postgres_1 psql -U "$U" -d "$D" "$@"
