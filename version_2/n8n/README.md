# n8n

Fluxo entre o Discord e o worker, em blocos visuais. Os fluxos ficam versionados em `workflows/` e são importados
e publicados por `scripts/n8n-deploy.sh`.

## Fluxos

| Fluxo | Disparo | O que faz |
|---|---|---|
| Cortes — entrada do Discord | Webhook `discord-in` (do bot) | Link novo → cria o corte no worker. Botão ou resposta → manda a ação (`approve`, `replan`, `revise`, `retry`, `cancel`). Responde ao bot com a mensagem para o canal |
| Cortes — eventos do worker | Webhook `job-events` (do worker) | Roteiro pronto → posta a prévia com Aprovar, Refazer e Cancelar. Vídeo pronto → posta a prévia do vídeo com Pedir alteração. Falha → posta o erro com Tentar de novo |

As mensagens são montadas nos nós **Mensagem: ...** (texto, cores e botões). Os endereços e tokens vêm das
variáveis do container (`$env.WORKER_URL`, `$env.WORKER_TOKEN`, `$env.BOT_URL`, `$env.BOT_API_TOKEN`), então os
fluxos não guardam segredos.

## Mudando um fluxo

- Pelo editor (`http://localhost:5678`): vale na hora, mas fica só no banco do n8n.
- Pelos arquivos de `workflows/`: rode `sh scripts/n8n-deploy.sh` (importa por cima e publica).

Para levar uma mudança feita no editor para o repositório, exporte o fluxo (menu ⋯ → Download) para
`workflows/`, mantendo o `id`.

## O que vem configurado

| Item | Como |
|---|---|
| Imagem | `docker.io/n8nio/n8n:stable` |
| Banco | SQLite no volume `n8n_data` |
| Acesso | `http://localhost:5678`, só na máquina |
| Isolamento | Telemetria e personalização desligadas |
| Fuso | `TZ` do `.env` (padrão `UTC`) |

Logs: `podman logs -f astroverso-studio_n8n_1`.
