#!/bin/sh
# uso: sh scripts/wait-video.sh <video_id>  — espera sair dos estados de processamento e mostra o resultado
cd "$(dirname "$0")/.."
ID=${1:-1}
for i in $(seq 1 60); do
  s=$(sh scripts/psql.sh -tAc "select state from videos where id=$ID")
  case "$s" in QUEUED|SCRIPTED|VOICED|VISUALS_READY|RENDERED) sleep 5;; *) break;; esac
done
sh scripts/psql.sh -c "select id, state, attempts, left(last_error, 1500) as err from videos where id=$ID" \
  -c "select from_state, to_state, note from video_events where video_id=$ID order by id"
