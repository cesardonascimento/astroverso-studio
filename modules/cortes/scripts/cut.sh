#!/bin/sh
# Cria um corte pelo terminal. uso: sh modules/cortes/scripts/cut.sh <link> [auto]  (auto = sem aprovação)
cd "$(dirname "$0")/../../.."
AUTO=false; [ "$2" = "auto" ] && AUTO=true
sh modules/cortes/scripts/api.sh POST /jobs "{\"url\": \"$1\", \"auto_approve\": $AUTO}"
