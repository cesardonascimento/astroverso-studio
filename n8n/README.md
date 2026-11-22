# n8n

O fluxo entre o Discord e os módulos, em blocos visuais. Os fluxos ficam versionados em `workflows/` e são
importados e publicados por `scripts/n8n-deploy.sh`.

## Fluxos

| Fluxo | Arquivo | Disparo | O que faz |
|---|---|---|---|
| Studio — entrada do Discord | `studio-entrada-discord.json` | Webhook `discord-in` (do bot) | Escolhe o módulo pelo campo `module` (Switch **Módulo**) e manda o pedido ou a ação para ele. Responde ao bot com a mensagem para o canal |
| Cortes — eventos | `cortes-eventos.json` | Webhook `cortes-events` (do módulo cortes) | Roteiro pronto → prévia com Aprovar, Refazer e Cancelar. Vídeo pronto → prévia do vídeo com Pedir alteração. Falha → erro com Tentar de novo |

As mensagens são montadas nos nós **Mensagem: ...** (texto, cores e botões). Os endereços e tokens vêm das
variáveis do container (`$env.CORTES_URL`, `$env.WORKER_TOKEN`, `$env.BOT_URL`, `$env.BOT_API_TOKEN`), então os
fluxos não guardam segredos.

## Mudando um fluxo

- Pelo editor (`http://localhost:5678`): vale na hora, mas fica só no banco do n8n.
- Pelos arquivos de `workflows/`: rode `sh scripts/n8n-deploy.sh` (importa por cima e publica).

Para levar uma mudança feita no editor para o repositório, exporte o fluxo (menu ⋯ → Download) para `workflows/`,
mantendo o `id`.

## O que vem configurado

| Item | Como |
|---|---|
| Imagem | `docker.io/n8nio/n8n:stable` |
| Banco | SQLite no volume `n8n_data` |
| Acesso | `http://localhost:5678`, só na máquina |
| Isolamento | Telemetria e personalização desligadas |
| Fuso | `TZ` do `.env` (padrão `UTC`) |

Logs: `podman logs -f astroverso-studio_n8n_1`.
