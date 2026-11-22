#!/bin/sh
# uso: sh scripts/cut.sh <url> [auto]   — cria um corte; com "auto" pula a aprovação do roteiro
cd "$(dirname "$0")/.."
AUTO=false; [ "$2" = "auto" ] && AUTO=true
sh scripts/api.sh POST /jobs "{\"url\": \"$1\", \"auto_approve\": $AUTO}"
