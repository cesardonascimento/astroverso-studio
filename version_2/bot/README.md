# bot

Bot do Discord que só leva e traz mensagens entre o canal do studio e o n8n. Não decide nada: o fluxo fica no n8n.

## Como funciona

```
Discord ⇄ bot ⇄ n8n (/webhook/discord-in) ⇄ worker
               ↖ n8n (POST /send)
```

| Do Discord | Vira |
|---|---|
| Mensagem com link no canal | `{"type": "new_cut", "url", "instructions"}` (o texto fora do link são as instruções) |
| Resposta a uma mensagem de corte | `{"type": "action", "action": "revise" ou "replan", "job_id", "text"}` |
| Botão | `{"type": "action", "action", "job_id"}`; Refazer e Pedir alteração abrem uma caixa de texto antes |

O n8n responde `{"message": "..."}` e o bot repassa no canal.

Os botões usam `custom_id` `cut:<ação>:<corte>`. Outros bots com o mesmo token não são afetados, desde que
ignorem esse prefixo. O número do corte vem do texto da mensagem ("Corte #N"), então os botões continuam
funcionando depois de reiniciar o bot.

## API para o n8n

`POST http://bot:8000/send`, com `Authorization: Bearer <BOT_API_TOKEN>`:

| Campo | O que é |
|---|---|
| `channel_id` | Canal (padrão: `DISCORD_CHANNEL_ID`) |
| `reply_to` | Mensagem a responder (o pedido original) |
| `content` | Texto, até 2000 caracteres |
| `embed` | `title`, `description`, `color`, `footer` |
| `file_path` | Arquivo relativo a `data/media` (só dentro dela) |
| `buttons` | Até 5: `label`, `custom_id`, `style` (`primary`, `success`, `danger`, `secondary`) |

## Requisitos no Discord

- **Message Content Intent** ligado no Developer Portal → Bot.
- Permissões no canal: ver, enviar mensagens, anexar arquivos, ler o histórico e adicionar reações.

Logs: `podman logs -f astroverso-studio_bot_1`.
