# bot

Ponte do studio com o Discord, compartilhada por todos os módulos. O bot em si é o **astroverso-discord** (o
`astro`), que atende vários projetos; esta ponte é o cliente `studio` dele. Só leva e traz mensagens entre o canal
e o n8n: não decide nada.

## Como funciona

```
Discord ⇄ astroverso-discord ⇄ ponte ⇄ n8n (/webhook/discord-in) ⇄ módulos
                                    ↖ n8n (POST /send)
```

Ao subir (e a cada 5 minutos), a ponte publica no astroverso-discord o canal que ela escuta (`STUDIO_DISCORD_CHANNEL`)
e o formato dos botões dela. Depois busca os eventos do cliente `studio` (`GET /v1/eventos`) e os entrega ao n8n:

| Do Discord | Vira |
|---|---|
| Mensagem com link no canal | `{"type": "new_request", "module": <STUDIO_DEFAULT_MODULE>, "url", "instructions"}` (o texto fora do link são as instruções) |
| Resposta a uma mensagem do bot | `{"type": "action", "module", "action": "revise" (mensagem com arquivo) ou "replan", "job_id", "text"}` |
| Botão | `{"type": "action", "module", "action", "job_id"}`; Refazer e Pedir alteração abrem uma caixa de texto antes |

O n8n responde `{"message": "..."}` e a ponte devolve ao astroverso-discord, que responde no canal.

Convenções dos módulos:

| Item | Formato |
|---|---|
| `custom_id` dos botões | `<módulo>:<ação>:<id>` (ex.: `cortes:approve:12`) |
| Rodapé das mensagens | `<módulo> #<id>`: é por ele que uma resposta é ligada ao job |

Os botões continuam funcionando depois de reiniciar o bot ou a ponte, porque tudo o que é preciso está no próprio
`custom_id`.

## API para o n8n

`POST http://bot:8000/send`, com `Authorization: Bearer <BOT_API_TOKEN>`:

| Campo | O que é |
|---|---|
| `channel_id` | Canal (padrão: o do studio) |
| `reply_to` | Mensagem a responder (o pedido original) |
| `content` | Texto, até 2000 caracteres |
| `embed` | `title`, `description`, `color`, `footer` |
| `file_path` | Arquivo relativo a `data/` (ex.: `cortes/jobs/5/render_v1/preview.mp4`), só dentro dela |
| `file_name` | Nome do anexo no Discord |
| `buttons` | Até 5: `label`, `custom_id`, `style` (`primary`, `success`, `danger`, `secondary`) |

A ponte traduz para `POST /v1/mensagens` do astroverso-discord (com o arquivo enviado junto) e devolve
`{"message_id"}`.

Logs: `podman logs -f astroverso-studio_bot_1`.
