#!/bin/sh
# Espera um corte sair das etapas de processamento e mostra o resultado. uso: sh modules/cortes/scripts/wait-job.sh <corte>
cd "$(dirname "$0")/../../.."
ID=${1:-1}
for i in $(seq 1 360); do
  s=$(sh scripts/psql.sh -tAc "select state from jobs where id=$ID")
  case "$s" in QUEUED|DOWNLOADED|TRANSCRIBED|APPROVED|RENDERED) sleep 5;; *) break;; esac
done
sh scripts/psql.sh -c "select id, state, attempts, left(last_error, 1500) as err from jobs where id=$ID" \
  -c "select from_state, to_state, note from job_events where job_id=$ID order by id"
