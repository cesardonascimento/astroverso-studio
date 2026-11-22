#!/bin/sh
# Cria um banco por módulo (STUDIO_DATABASES, separados por espaço) na primeira inicialização do Postgres.
set -e
for db in $STUDIO_DATABASES; do
  echo "[studio] criando banco $db"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres -c "CREATE DATABASE \"$db\""
done
