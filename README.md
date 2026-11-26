# Astroverso Studio

## O que é

Estúdio de vídeos com IA, num app web próprio. Você escolhe um algoritmo de geração, as redes de destino e a
estratégia de cada uma; a IA produz o roteiro, você aprova ou edita, e recebe o vídeo pronto.

- **Guarda-chuva:** três peças num repositório: o app (`studio`), o banco (Postgres) e o armazenamento de vídeos (S3).
  Sobem juntas numa máquina ou separadas, com o banco e o S3 num PC que faz papel de NAS.
- **Várias instâncias, mesmos dados:** duas ou mais máquinas com o app apontam para o mesmo banco e o mesmo S3. Cada
  uma processa as próprias gerações e todas veem tudo.
- **Algoritmos, redes e estratégias:** cada pedido usa um algoritmo de geração e uma ou mais redes de destino. Cada
  rede tem formato, duração e estratégias próprias (viral, emotivo, motivador, informativo...), escritas em `.md`. Na
  estratégia **Auto**, a IA escolhe a que mais combina com o vídeo. Cada versão do roteiro guarda o texto da
  estratégia usada.
- **Fila por instância:** cada etapa é um job com até 3 tentativas (espera de 1, 4 e 16 minutos entre elas). Uma falha
  definitiva fica registrada no histórico da geração.
- **Vídeos como arquivos comuns:** o S3 (versitygw) grava cada objeto como arquivo numa pasta do disco, fácil de
  navegar e de copiar para backup.

- **Nova geração em três passos:** escolha o algoritmo, preencha o pedido (os campos vêm do algoritmo) e marque as
  redes, com estratégia, enquadramento, legenda e a opção de renderizar sem esperar a aprovação.
- **Acompanhar e aprovar:** a página da geração mostra as etapas ao vivo (atualiza sozinha enquanto há algo em
  andamento) e o histórico. O roteiro de cada rede pode ser editado antes de aprovar: título, texto da tela, legenda,
  hashtags e o início e o fim de cada trecho (ajustados às palavras). Também dá para pedir outro roteiro com
  instruções, cancelar e tentar de novo uma etapa que falhou.
- **Resultado:** player (lê do S3 pelo app, com avanço no vídeo), download com o nome `yyyyMMddHHmm - título.mp4`,
  versões anteriores, pedido de alteração (muda só o que foi pedido e renderiza direto) e render de novo com outro
  enquadramento ou legenda, sem chamar a IA.
- **Apagar o original:** libera o espaço do vídeo baixado do YouTube. Os cortes prontos ficam; novos roteiros e renders
  daquela geração deixam de ser possíveis.
- **Listagem:** todas as gerações de todas as instâncias, com filtros por situação e por instância e o custo da IA.
- **Estratégias editáveis pelo site:** criar, editar (com prévia do markdown), apagar, importar e exportar no formato
  `SKILL.md` (`name` e `description` no cabeçalho). A página grava os arquivos em `studio/content/`; para guardar no
  git, faça commit.
- **Página com login:** uma senha só (`STUDIO_PASSWORD`), cookie assinado por 30 dias. Tema claro e escuro.

### Algoritmos

- **Corte de vídeo (`corte`):** recebe o link de um vídeo longo do YouTube e instruções opcionais. Baixa o vídeo,
  transcreve (legenda automática do YouTube com tempo por palavra; sem legenda, Whisper), e o Claude escolhe de 1 a 4
  trechos, o texto da tela, a legenda do post e as hashtags, seguindo a rede e a estratégia. As bordas dos trechos são
  ajustadas às palavras reais. Depois da aprovação, monta o vídeo vertical 1080x1920 com legendas palavra por
  palavra, volume normalizado (-14 LUFS) e controle de qualidade. Numa revisão, os trechos que não mudaram são
  copiados da versão anterior, para as bordas não "andarem".

## Como usar

### Requisitos

Linux com Podman e `podman-compose`.

### Instalação numa máquina só

```bash
cp .env.example .env                       # troque todos os toBeModified
mkdir -p data/db data/s3 data/work
podman-compose --profile storage --profile studio up -d --build
```

A página fica em `http://<ip>:<STUDIO_PORT>`.

### Banco e S3 num PC-NAS

No PC-NAS:

```bash
cp .env.example .env                       # DATABASE_PASSWORD, S3_ACCESS_KEY e S3_SECRET_KEY
                                           # STORAGE_BIND_ADDRESS=0.0.0.0
                                           # DATABASE_DATA_DIR e S3_DATA_DIR na pasta do disco
mkdir -p <DATABASE_DATA_DIR> <S3_DATA_DIR>
podman-compose --profile storage up -d
```

Nas máquinas com o app, o `.env` usa as mesmas senhas e aponta para o PC-NAS: `DATABASE_HOST=<ip>` e
`S3_ENDPOINT=http://<ip>:7070`. Cada máquina tem um `INSTANCE_NAME` diferente.

### `.env`

| Variável | O que é |
|---|---|
| `INSTANCE_NAME` | Nome desta instância. Diferente em cada máquina que compartilha os dados |
| `STUDIO_PORT` | Porta da página |
| `STUDIO_PASSWORD` | Senha de acesso à página |
| `SECRET_KEY` | Chave que assina o cookie de login. Gere com `openssl rand -hex 32` |
| `TZ` | Fuso dos horários, no formato `<região>/<cidade>` |
| `CONTENT_LANGUAGE` | Idioma dos textos gerados |
| `WORK_DATA_DIR` | Pasta local de trabalho (download, transcrição, render). Pode ser apagada com o app parado |
| `STORAGE_BIND_ADDRESS` | Onde o banco e o S3 escutam. `127.0.0.1` numa máquina só; `0.0.0.0` num PC-NAS |
| `DATABASE_*` | Endereço, porta, nome, usuário, senha e pasta de dados do Postgres |
| `S3_*` | Endereço, porta, bucket, chaves e pasta de dados do S3. A porta de `S3_ENDPOINT` é a mesma de `S3_PORT` |
| `ANTHROPIC_API_KEY` | Chave da API do Claude: https://console.anthropic.com → API Keys |
| `LLM_MODEL` | Modelo do Claude |
| `WHISPER_MODEL` | Modelo de transcrição: `small`, `medium` ou `large-v3` |
| `WHISPER_DEVICE` | `auto` (GPU se houver), `cuda` ou `cpu` |
| `WHISPER_COMPUTE_TYPE` | `auto` (`int8_float16` na GPU, `int8` na CPU) ou outro tipo do faster-whisper |
| `YOUTUBE_COOKIES_FILE` | Cookies do navegador, se o YouTube pedir login. Vazio na maioria dos casos |
| `WEBDAV_*` | Destino dos vídeos prontos (Nextcloud ou outro WebDAV). `WEBDAV_URL` vazio desliga o envio |

## Como desenvolver

### Peças

- **`compose.yaml`:** perfil `storage` com `db` (Postgres) e `s3` (versitygw no modo `posix`); perfil `studio` com o
  app.
- **`studio/`:** o app (FastAPI). `Containerfile` com Python, FFmpeg, a fonte das legendas e o Deno que o yt-dlp usa.
- **`studio/content/`:** o conteúdo editável, versionado no git:
  - `algorithms/<algoritmo>/*.md`: os prompts de cada algoritmo;
  - `networks/<rede>/network.md`: formato, duração, legenda, hashtags e preset de legenda da rede, mais a orientação
    para a IA no corpo;
  - `networks/<rede>/strategies/*.md`: uma estratégia por arquivo, com `name` e `description` no cabeçalho e o texto
    no corpo;
  - `subtitles/*.md`: um preset de legenda por arquivo (fonte, tamanho, cores, palavras por vez).

### Camadas do app

- **`app/config.py`:** o único lugar que lê variáveis de ambiente. Toda variável nova entra também no `.env.example`.
- **`app/models/`:** as tabelas (SQLAlchemy), só dados. `Generation` é um pedido; `Output` é o resultado dele para
  uma rede; `OutputVersion` guarda cada versão do roteiro com a estratégia usada e o vídeo; `Job` é a fila de
  etapas, sempre de uma instância; `Event` é o histórico mostrado na página; `Export` é um envio; `LlmCall` é o custo
  de cada chamada à IA.
- **`migrations/`:** migrações do Alembic, aplicadas sozinhas quando o app sobe. Depois de mudar um model, gere uma
  nova com `alembic revision --autogenerate -m "<o que mudou>"` (dentro da imagem de teste) e revise o arquivo.
- **`app/lib/`:** integração com o que é de fora e não é IA. Recebe parâmetros e devolve resultados, sem conhecer
  models nem services. Cada operação é uma classe com `execute`.
  - **`lib/database`:** abre sessões e aplica as migrações.
  - **`lib/s3`:** garante o bucket, envia, baixa, lê (com faixa de bytes, para o player) e apaga objetos.
  - **`lib/youtube`:** baixa o vídeo (até 1080p, preferindo H.264) e as legendas do YouTube com tempo por palavra.
  - **`lib/ffmpeg`:** mede vídeos, extrai o áudio, monta o corte vertical 1080x1920 (layouts `crop`, `fit_blur`,
    `split` ou `auto`), queima as legendas ASS palavra por palavra, normaliza o volume e confere a qualidade.
  - **`lib/media.py`:** `Word` e `Segment`, os tipos que circulam entre `lib/` e `ai/`.
  - **`lib/content`:** lê e grava os `.md` com cabeçalho (frontmatter).
- **`app/ai/`:** tudo que é IA, com a mesma regra da `lib/`.
  - **`ai/claude`:** uma chamada que devolve JSON validado por um model Pydantic, com o uso de tokens e o custo.
  - **`ai/whisper`:** transcrição com tempo por palavra (faster-whisper), na GPU quando houver.

- **`app/controllers/`:** rotas por área. Recebem a requisição, chamam um service e renderizam uma view. Sem regra de
  negócio. `require_login.py` protege tudo, menos `/login`, `/static` e `/health` (pedidos do htmx recebem
  `HX-Redirect`).
- **`app/views/`:** templates Jinja2. `layout.html` tem o menu; `macros.html` tem `icon()` e `state_badge()`;
  `icons/` guarda só os SVGs usados (Tabler Icons).
- **`app/static/`:** `css/studio.css` e `vendor/` com Tabler, htmx e Alpine.js versionados, sem build.
- **`app/dependencies.py`:** monta as peças de `lib/` e `ai/` com as configurações (cliente do S3, Claude, Whisper,
  YouTube). Nos testes, é aqui que se troca uma peça por uma falsa.
- **`app/services/<domínio>/`:** as regras do studio, uma classe por feature com um método `execute`.
  - **`catalog`:** lê redes, estratégias e presets de legenda de `content/`.
  - **`generations`:** cria uma geração (valida os campos do algoritmo e as estratégias e põe a primeira etapa na fila),
    transforma o formulário em destinos (`BuildTargets`), lista com filtros e apaga o original.
  - **`outputs`:** aprovar (com edição, que vira uma nova versão), pedir outro roteiro ou uma alteração, renderizar de
    novo, cancelar, tentar de novo, abrir o vídeo e montar o nome do arquivo.
  - **`strategies`:** salva, apaga, importa e exporta estratégias como `.md` e gera a prévia do markdown (HTML do
    texto é escapado).
  - **`jobs`**, **`events`**, **`costs`:** fila, histórico e custo das chamadas à IA.
- **`app/algorithms/`:** os algoritmos de geração. `base.py` define o contrato: campos do formulário, etapas de
  preparação (uma vez por geração), a etapa de roteiro, as etapas de render (uma vez por rede), o template que mostra
  o roteiro (`views/algorithms/<nome>/plan.html`) e o editor que aplica as edições da página. Cada etapa é uma
  classe com `name`, `label` e `execute(context)`, que devolve a mensagem do histórico; `StepFailed` encerra sem novas
  tentativas.
- **`app/worker/`:** reserva o próximo job da instância (`FOR UPDATE SKIP LOCKED`), roda a etapa e decide a próxima:
  preparação → roteiro de cada rede → aprovação (ou direto, com `auto_approve` e nas revisões) → render → pronto.

### Como criar um algoritmo

1. Criar `app/algorithms/<nome>/` com as etapas, o editor do roteiro e um `Algorithm` em `algorithm.py`, e o
   template `app/views/algorithms/<nome>/plan.html`.
2. Registrar em `app/algorithms/__init__.py`.
3. Colocar os prompts em `content/algorithms/<nome>/`.
4. Descrever o algoritmo na seção **Algoritmos** deste README.

### Como criar uma rede ou uma estratégia

- **Rede:** uma pasta `content/networks/<rede>/` com `network.md` e pelo menos uma estratégia.
- **Estratégia:** pela página **Estratégias** ou com um `.md` em `content/networks/<rede>/strategies/`. Ela aparece
  no formulário e no modo Auto.

### Testes

```bash
sh scripts/test.sh            # usa o .env; precisa do perfil storage rodando
```

Os testes usam um banco separado (`<DATABASE_NAME>_test`), recriado a cada rodada. Eles conferem, entre outras coisas, que o `.env.example` lista todas as variáveis usadas pelo app e pelo
`compose.yaml`.
