# astroverso-studio — v1 (vídeos narrados a partir de tendências)

Pipeline de criação de vídeos curtos (TikTok, pt-BR) a partir de tendências reais.

```
Creative Center do TikTok (via Apify)      ← tendências BR (hashtags) + vídeos de referência (US)
        ↓
Claude: agrupa em TEMAS (busca na web p/ hashtags desconhecidas)
        ↓
Claude: gera ~20 IDEIAS com notas por critério → código calcula o score final
        ↓
você escolhe (Fase 1)                       ← POST /videos {idea_id}
        ↓
fila no Postgres (máquina de estados, retomável)
  QUEUED → roteiro + revisão → SCRIPTED → voz → VOICED → imagens → VISUALS_READY
        → FFmpeg → RENDERED → QC → READY_FOR_REVIEW | QC_FAILED
        ↓
você aprova → (próxima etapa: TikTok Content Posting API, modo rascunho)
```

## Serviços (tudo em container, dentro do WSL)

| serviço  | função | porta (só localhost) |
|----------|--------|-------|
| postgres | estado, fila, métricas, custo | 5432 |
| worker   | Python/FastAPI + FFmpeg: LLM, TTS, imagens, render, QC | 8090 |
| n8n      | agendamento, aprovação, notificações (chama o worker por HTTP) | 5678 |

Decisão de arquitetura: a lógica de IA (prompts, providers, scoring) fica **no worker**, não em nós do n8n.
Código versionado e testável, troca de provider num lugar só. O n8n orquestra: cron, aprovação humana, retries de alto nível, avisos.

## Rodar

```sh
# no Fedora do WSL
cd version_1
cp .env.example .env        # já existe um .env com senhas geradas; preencha as chaves
podman-compose up -d --build
```

Utilitários (rodar no WSL):

```sh
sh scripts/api.sh GET /health
sh scripts/psql.sh -c "select id, state from videos"
sh scripts/wait-video.sh 1
```

## Uso (Fase 1 — humano no loop)

```sh
sh scripts/api.sh POST /trends/refresh '{}'              # busca tendências + temas
sh scripts/api.sh POST /ideas/generate '{"count":20}'    # gera e ranqueia ideias
sh scripts/api.sh GET  "/ideas?limit=10"                 # top 10
sh scripts/api.sh POST /videos '{"idea_id": 7}'          # produz (idempotente)
sh scripts/api.sh GET  /videos/1                         # estado, roteiro, eventos, custo
# vídeo pronto em data/media/videos/<id>/final.mp4
sh scripts/api.sh POST /videos/1/approve                 # ou reject / retry / cancel
```

Experimentos: `POST /videos {"idea_id": 7, "settings": {"voice": "pt-BR-FranciscaNeural", "rate": "+20%", "visual_style": "cinematic, moody"}}` — as variáveis ficam gravadas em `videos.settings` para comparar com as métricas depois.

## Providers (trocáveis via .env)

| etapa | atual | por quê | troca futura |
|-------|-------|---------|--------------|
| tendências | Apify `data_xplorer~tiktok-trends` (Creative Center) | o TikTok não tem API oficial de tendências para uso comercial (a Research API é só acadêmica). ~US$0,50–2 / 1.000 resultados | outro actor, ou fonte própria |
| LLM | Claude (`LLM_MODEL`, padrão `claude-opus-5-5`) | structured outputs + busca web nativa | `claude-sonnet-5-5` / `claude-haiku-5-5` para baratear |
| voz | edge-tts (vozes neurais Microsoft) | grátis, ótimo pt-BR, tempo por palavra p/ legendas. **Não oficial** | Azure Speech (mesmas vozes, oficial, 0,5M caracteres/mês grátis) ou ElevenLabs |
| imagens | `placeholder` → `pexels` | Pexels: API oficial grátis, licença comercial | FLUX.2 klein 4B local na RTX 5070 (precisa do nvidia-container-toolkit no WSL) |
| vídeo IA | — | caro e desnecessário para validar | Fase posterior, só nas cenas-chave |

Fallback de segurança do Claude: as chamadas usam `fallbacks: "default"` (beta `server-side-fallback-2026-07-01`). Se o modelo recusar por falso positivo, o servidor tenta outro modelo automaticamente.

## Score das ideias

O LLM dá notas de 0 a 10 por critério. O **código** calcula o score final (`worker/app/scoring.py`):

```
base       = 10 × Σ(peso × nota)     hook .20, curiosidade .15, retenção .15, tendência .15,
                                     originalidade .10, compartilhamento .10, comentário .05,
                                     clareza .05, facilidade .05
penalidade = 2×risco_repetição + 3×risco_conteúdo + 60×max(0, similaridade − 0.35)
final      = base − penalidade
auto_rejected se risco_conteúdo ≥ 7 ou similaridade (pg_trgm) ≥ 0.6 com ideias anteriores
```

## Custo estimado (validação)

Por vídeo, estimativa aproximada: **~US$0,10–0,30**. Quase tudo é Claude Opus 5.5 (roteiro + revisão + parte do lote de ideias e da análise de tendências). Voz e imagens: grátis. Apify: ~US$0,10 por atualização de tendências.
Com `claude-haiku-5-5` cai bastante. O custo real de cada chamada fica em `generations` (`GET /videos/{id}` mostra `cost_usd`).

## Estrutura

```
compose.yaml, .env(.example)
db/init/          cria o banco do n8n (1ª inicialização)
db/migrations/    SQL versionado, aplicado pelo worker ao subir
prompts/          prompts versionados (1ª linha = version)
config/           manual_trends.json (fonte de tendências manual)
worker/app/
  main.py         API
  jobs.py         fila + máquina de estados (FOR UPDATE SKIP LOCKED, lease, backoff)
  llm.py          camada LLM (structured outputs, custo)
  scoring.py      ranking explicável
  qc.py           quality control
  pipeline/       trends, ideas, production (etapas idempotentes)
  providers/      trends, tts, images
  render/         ffmpeg, subtitles (.ass estilo TikTok)
n8n/workflows/    (próximo passo) workflows exportados
scripts/          utilitários de shell
data/media/       saída (vídeos, assets)
```

## Próximos passos

1. Chaves: `ANTHROPIC_API_KEY`, `APIFY_TOKEN`, `PEXELS_API_KEY` → rodar o fluxo completo com tendências reais.
2. n8n: workflow diário (refresh → ideias → aviso no Telegram com top 10 → escolha → aviso de vídeo pronto).
3. Imagens com IA local (FLUX.2 klein) ou API barata.
4. TikTok: app no developer portal, OAuth, Content Posting API em modo **rascunho (inbox)**, tabela `publications` com idempotency key.
5. Métricas (Display API) → `metrics` → insights → prompts.
