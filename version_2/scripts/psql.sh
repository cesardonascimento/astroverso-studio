#!/bin/sh
cd "$(dirname "$0")/.."
U=$(grep ^POSTGRES_USER= .env | cut -d= -f2); D=$(grep ^POSTGRES_DB= .env | cut -d= -f2)
exec podman exec -i astroverso-studio_postgres_1 psql -U "$U" -d "$D" "$@"
