#!/bin/sh
set -e
cd "$(dirname "$0")/.."
ENV_FILE=${1:-.env}
. "./$ENV_FILE"
podman build -q --target test -t studio-test studio >/dev/null
podman run --rm --network host --env-file "$ENV_FILE" \
  -e DATABASE_HOST="$(echo "$DATABASE_HOST" | sed 's#^db$#127.0.0.1#')" \
  -e S3_ENDPOINT="$(echo "$S3_ENDPOINT" | sed 's#//s3:#//127.0.0.1:#')" \
  -v .:/repo:Z -w /repo/studio studio-test python -m pytest -q
