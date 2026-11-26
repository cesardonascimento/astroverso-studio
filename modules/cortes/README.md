# cortes

Módulo de cortes de vídeos longos para o TikTok. Recebe o link de um vídeo do YouTube, usa a transcrição para o
Claude escolher o melhor trecho, espera a sua aprovação e monta o corte vertical com legendas palavra por palavra.

## Como usar

Pelo terminal ou pela API (abaixo). O arquivo final, em 1080x1920, fica em
`data/cortes/jobs/<corte>/render_v<versão>/final.mp4`.

## Variáveis do `.env`

- **`CUT_MAX_DURATION_S`:** duração máxima de um corte, em segundos. Padrão: `75`. Um pedido no próprio link
  ("máximo 40s") vale mais.
- **`CUT_LAYOUT`:** como o vídeo horizontal vira vertical. Padrão: `auto` (ver Layouts).
- **`WHISPER_MODEL`:** o modelo de transcrição local, usado só quando o YouTube não tem legenda. Padrão: `small`.
  Maiores (`medium`, `large-v3`) acertam mais e demoram mais.
- **`YOUTUBE_COOKIES_FILE`:** cookies do navegador, se o YouTube pedir login. Vazio na maioria dos casos.
- **`CONTENT_LANGUAGE`:** idioma dos textos gerados. Padrão: `pt-BR`.

## Personalizar sem programar

| O quê | Onde |
|---|---|
| Como a IA escolhe o corte | `prompts/clip_plan.md` |
| Como a IA aplica alterações | `prompts/clip_revise.md` |
| Estilos de legenda (`padrao`, `grande`, `verde`, `minimalista`), duração e layout padrão | `config/presets.json` (vale no próximo vídeo) |

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

Cada etapa roda numa fila no próprio Postgres (`FOR UPDATE SKIP LOCKED`), com reserva de 60 minutos, 3 tentativas
e espera de 1, 4 e 16 minutos entre elas. Esgotadas, o corte vai para `FAILED` e o `retry` continua da etapa em que
parou.

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

## Efeitos

`app/render/effects/` é o registro de efeitos de edição. O roteiro tem a lista `edits` (tipo, início, fim,
parâmetros), e a IA só pode usar efeitos registrados. Para criar um: uma subclasse de `Effect` com `@register`, que
devolve o filtro do FFmpeg. Nenhum efeito implementado ainda.

## API

Todas as rotas, menos `/health`, pedem `Authorization: Bearer <WORKER_TOKEN>`. Na máquina: `http://localhost:8091`.

| Rota | O que faz |
|---|---|
| `POST /jobs` | Cria um corte: `url`, `instructions`, `auto_approve`, `layout`, `subtitle_preset`, `context` |
| `GET /jobs` · `GET /jobs/{id}` | Lista · detalhe com eventos |
| `GET /jobs/{id}/preview` | Roteiro em texto |
| `GET /jobs/{id}/plans` | Versões |
| `GET /jobs/{id}/file` (`?preview=1`) | Vídeo final (ou a prévia) |
| `POST /jobs/{id}/<ação>` | `approve`, `replan`, `revise`, `rerender`, `retry`, `cancel`; texto em `text` |
| `GET /presets` | Presets e efeitos disponíveis |

## Pelo terminal

```bash
sh modules/cortes/scripts/cut.sh "<link>" auto     # corte direto, sem aprovação
sh modules/cortes/scripts/wait-job.sh <corte>      # espera terminar e mostra as etapas
sh modules/cortes/scripts/api.sh GET /jobs/<corte>/preview
```

## Arquivos gerados

| Caminho | Conteúdo |
|---|---|
| `data/cortes/jobs/<id>/source.mp4` | Vídeo original |
| `data/cortes/jobs/<id>/info.json` | Metadados do YouTube |
| `data/cortes/jobs/<id>/transcript_*.json` | Transcrição com tempo por palavra |
| `data/cortes/jobs/<id>/render_v<n>/final.mp4` | Corte final da versão `n` |
| `data/cortes/jobs/<id>/render_v<n>/preview.mp4` | Prévia de até 9 MB |
| `data/cortes/jobs/<id>/render_v<n>/subs.ass` | Legendas |

Logs: `podman logs -f astroverso-studio_cortes_1`.
