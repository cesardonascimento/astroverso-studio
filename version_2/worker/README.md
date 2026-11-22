# worker

API em Python (FastAPI) que produz os cortes: download, transcrição, escolha do trecho pelo Claude, montagem com
o FFmpeg e controle de qualidade. Guarda o estado de cada corte no Postgres e avisa o n8n a cada mudança.

## Etapas

```
QUEUED → DOWNLOADED → TRANSCRIBED → AWAITING_APPROVAL → APPROVED → RENDERED → DONE
                                     (aprovação)                     (QC)   ↘ QC_FAILED
```

| Etapa | O que faz |
|---|---|
| Download | `yt-dlp`, até 1080p, preferindo H.264 |
| Transcrição | Legenda automática do YouTube na língua original (tempo por palavra); senão a manual; senão Whisper local |
| Roteiro | O Claude escolhe de 1 a 4 trechos, o texto da tela, a legenda do post e alternativas. As bordas são ajustadas às palavras reais |
| Aprovação | Espera o Aprovar, a não ser com `auto_approve` |
| Render | Corta os trechos, enquadra em 1080x1920, queima as legendas, normaliza o volume (-14 LUFS) e gera a prévia leve |
| QC | Resolução, codec, áudio, tela preta, silêncio e legendas |

Cada etapa roda numa fila no próprio Postgres (`FOR UPDATE SKIP LOCKED`), com reserva de 60 minutos, 3
tentativas e espera de 1, 4 e 16 minutos entre elas. Esgotadas, o corte vai para `FAILED` e o `retry` continua
da etapa em que parou.

## Alterações

| Ação | Quando | O que faz |
|---|---|---|
| `approve` | roteiro pronto | Renderiza |
| `replan` | antes ou depois do vídeo | Roteiro novo com o pedido; volta para aprovação |
| `revise` | vídeo pronto | Muda só o que foi pedido e renderiza direto |
| `rerender` | vídeo pronto | Renderiza de novo com outro layout ou preset, sem chamar a IA |
| `retry` / `cancel` | falhou / qualquer | Retoma / cancela |

Cada versão fica em `job_plans`, com o pedido que a gerou e o vídeo dela. Na revisão, um trecho que volta igual é
copiado da versão anterior, para as bordas não "andarem" a cada pedido.

## Layouts

| Layout | Quando usar | Opções |
|---|---|---|
| `auto` | Padrão: vídeo vertical → `crop`; horizontal → `fit_blur` | — |
| `crop` | Uma pessoa, tela cheia | `crop_x`: 0 esquerda, 0.5 centro, 1 direita |
| `fit_blur` | Vídeo inteiro, fundo desfocado | — |
| `split` | React ou duas câmeras, uma região em cima e outra embaixo | `top_box`, `bottom_box`: `[x, y, largura, altura]` de 0 a 1 |

## Presets e efeitos

- `config/presets.json`: estilos de legenda (`padrao`, `grande`, `verde`, `minimalista`), layout e duração
  padrão. Lido a cada render. A IA pode trocar o preset quando o pedido for visual ("legenda maior").
- `app/render/effects/`: registro de efeitos de edição. O roteiro tem a lista `edits` (tipo, início, fim,
  parâmetros), e a IA só pode usar efeitos registrados. Para criar um: uma subclasse de `Effect` com `@register`,
  que devolve o filtro do FFmpeg. Nenhum efeito implementado ainda.

## API

Todas as rotas, menos `/health`, pedem `Authorization: Bearer <WORKER_TOKEN>`.

| Rota | O que faz |
|---|---|
| `POST /jobs` | Cria um corte: `url`, `instructions`, `auto_approve`, `layout`, `subtitle_preset`, `context` |
| `GET /jobs` · `GET /jobs/{id}` | Lista · detalhe com eventos |
| `GET /jobs/{id}/preview` | Roteiro em texto |
| `GET /jobs/{id}/plans` | Versões |
| `GET /jobs/{id}/file` (`?preview=1`) | Vídeo final (ou a prévia) |
| `POST /jobs/{id}/<ação>` | `approve`, `replan`, `revise`, `rerender`, `retry`, `cancel`; texto em `text` |
| `GET /presets` | Presets e efeitos disponíveis |

A cada mudança de estado, o worker manda ao n8n (`N8N_EVENTS_URL`) o evento com o resumo do corte. Falhas nesse
aviso nunca param o corte.

## Arquivos gerados

| Caminho | Conteúdo |
|---|---|
| `data/media/jobs/<id>/source.mp4` | Vídeo original |
| `data/media/jobs/<id>/info.json` | Metadados do YouTube |
| `data/media/jobs/<id>/transcript_*.json` | Transcrição com tempo por palavra |
| `data/media/jobs/<id>/render_v<n>/final.mp4` | Corte final da versão `n` |
| `data/media/jobs/<id>/render_v<n>/preview.mp4` | Prévia de até 9 MB |
| `data/media/jobs/<id>/render_v<n>/subs.ass` | Legendas |

Logs: `podman logs -f astroverso-studio_worker_1`.
