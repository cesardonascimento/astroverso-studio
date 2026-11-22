# bot

Bot do Discord do studio, compartilhado por todos os módulos. Só leva e traz mensagens entre o canal e o n8n: não
decide nada.

## Como funciona

```
Discord ⇄ bot ⇄ n8n (/webhook/discord-in) ⇄ módulos
               ↖ n8n (POST /send)
```

| Do Discord | Vira |
|---|---|
| Mensagem com link no canal | `{"type": "new_request", "module": <STUDIO_DEFAULT_MODULE>, "url", "instructions"}` (o texto fora do link são as instruções) |
| Resposta a uma mensagem do bot | `{"type": "action", "module", "action": "revise" (mensagem com arquivo) ou "replan", "job_id", "text"}` |
| Botão | `{"type": "action", "module", "action", "job_id"}`; Refazer e Pedir alteração abrem uma caixa de texto antes |

O n8n responde `{"message": "..."}` e o bot repassa no canal.

Convenções dos módulos:

| Item | Formato |
|---|---|
| `custom_id` dos botões | `<módulo>:<ação>:<id>` (ex.: `cortes:approve:12`) |
| Rodapé das mensagens | `<módulo> #<id>`: é por ele que uma resposta é ligada ao job |

Botões em outro formato (ex.: de outro bot com o mesmo token) são ignorados. Os botões continuam funcionando depois
de reiniciar o bot, porque tudo o que ele precisa está no próprio `custom_id`.

## API para o n8n

`POST http://bot:8000/send`, com `Authorization: Bearer <BOT_API_TOKEN>`:

| Campo | O que é |
|---|---|
| `channel_id` | Canal (padrão: `DISCORD_CHANNEL_ID`) |
| `reply_to` | Mensagem a responder (o pedido original) |
| `content` | Texto, até 2000 caracteres |
| `embed` | `title`, `description`, `color`, `footer` |
| `file_path` | Arquivo relativo a `data/` (ex.: `cortes/jobs/5/render_v1/preview.mp4`), só dentro dela |
| `file_name` | Nome do anexo no Discord |
| `buttons` | Até 5: `label`, `custom_id`, `style` (`primary`, `success`, `danger`, `secondary`) |

## Requisitos no Discord

- **Message Content Intent** ligado no Developer Portal → Bot.
- Permissões no canal: ver, enviar mensagens, anexar arquivos, ler o histórico e adicionar reações.

Logs: `podman logs -f astroverso-studio_bot_1`.
