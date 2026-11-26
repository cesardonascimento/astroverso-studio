# CLAUDE.md

Regras para desenvolver o Astroverso Studio. O contexto da instalação atual (máquina, GPU, rede) fica em
`CLAUDE.local.md`, fora do git.

## Situação

O studio é um projeto próprio, independente do Astroverso, que roda em qualquer máquina com GPU. A prova de conceito
antiga (módulo `cortes`, ponte com o Discord, n8n) fica no histórico do git; `archive/tendencias` é só histórico.

## Arquitetura decidida

- **Guarda-chuva:** um repositório com três peças e um `compose.yaml` com perfis. `studio/` é o app (perfil
  `studio`); `s3/` (versitygw gravando numa pasta do disco) e `db/` (Postgres) formam o perfil `storage`. Numa máquina
  só, sobem os dois perfis; num PC-NAS, só `storage`, e as instâncias do app apontam para ele.
- **Monolito:** FastAPI com views Jinja2 renderizadas no servidor, Tabler + htmx + Alpine.js versionados em
  `static/vendor/`. Sem Node e sem build.
- **Sempre Postgres + S3**, mesmo numa máquina só. Não existe modo SQLite nem armazenamento local.
- **Várias instâncias, mesmos dados:** cada geração guarda a instância que a criou (`INSTANCE_NAME`) e o worker de
  cada instância só processa as próprias gerações. Aprovar ou pedir alteração funciona de qualquer instância.
- **Arquivos:** o trabalho (download, transcrição, render) acontece em `WORK_DIR`, local; os resultados sobem para o
  S3. Player e download passam pelo app, que lê do S3.
- **Conteúdo em `.md`, versionado:** prompts, redes, estratégias e presets de legenda ficam em `studio/content/`. O
  banco guarda só o estado das gerações, versões de roteiro, eventos, envios e custos.
- **Fluxo:** algoritmo (hoje só o corte de vídeo do YouTube) → redes de destino, cada uma com uma estratégia (ou
  Auto) → geração → aprovação/edição do roteiro → resultado → envio por WebDAV (`yyyyMMddHHmm - título.mp4` + `.txt`
  com legenda e hashtags).
- **Whisper na GPU NVIDIA** (faster-whisper com CUDA): a GPU entra no Podman por CDI. Com 4 GB de VRAM, `medium` ou
  `large-v3` em `int8_float16`; sem GPU, CPU em `int8`.
- **Só a API da Anthropic** para o Claude.

## Camadas do app

| Pasta | O que vai nela |
|---|---|
| `models/` | Tabelas (SQLAlchemy). Só dados |
| `controllers/` | Rotas por área: recebem a requisição, chamam um service, renderizam uma view |
| `views/` | Templates Jinja2: páginas e partials do htmx |
| `services/<domínio>/` | Só as regras de negócio do studio. Uma classe por feature |
| `algorithms/<nome>/` | Um algoritmo de geração e suas etapas, uma classe por etapa |
| `worker/` | Fila: reserva o próximo job da instância, roda a etapa, trata falhas e novas tentativas |
| `ai/<ferramenta>/` | Tudo que é IA: Claude, Whisper e o que vier |
| `lib/<serviço>/` | Integração com tudo que é de fora e não é IA: banco (sessão, engine), S3, YouTube, FFmpeg, WebDAV, TikTok |
| `content/` | Os `.md` versionados |
| `dependencies.py` | Monta as peças de `lib/` e `ai/` com as configurações |

## Regras de código

- Uma classe por feature, com um único método público (`execute`). Nada de classes com várias funções públicas.
- Controllers não têm regra de negócio. Services não falam com o mundo de fora direto: usam `lib/` e `ai/`.
- `lib/` e `ai/` não conhecem services nem models: recebem parâmetros e devolvem resultados, para serem reutilizados.
- O Claude fica em `ai/claude`, não em `lib/`. O banco e o S3 ficam em `lib/`, não em `services/`.
- Clean code e **nenhum comentário no código**. Nomes claros no lugar de comentários; armadilhas vão para a seção
  Armadilhas deste arquivo.

## Variáveis de ambiente

- `studio/app/config.py` é o único lugar que lê o ambiente.
- O `.env.example` lista **todas** as variáveis usadas (app, banco e S3). Um teste quebra se faltar alguma.
- Valores padrão não sensíveis ficam preenchidos; senhas, tokens e chaves usam `toBeModified`.

## Documentação

- **README.md**, em três seções:
  - **O que é:** cada feature e cada algoritmo, em título + descrição curta.
  - **Como usar:** instalação e configuração exatas.
  - **Como desenvolver:** cada camada em título + explicação.
- Todo algoritmo novo entra no README.
- Só o que é importante e relevante para o desenvolvimento. Nada de texto de enchimento.
- Armadilhas vão aqui no `CLAUDE.md`, não no código.

## Como trabalhar

- Responder sempre em **português do Brasil**, de forma direta.
- **Micro commits.** Um pedaço pequeno por vez: primeiro descrever a arquitetura daquele pedaço e esperar a
  aprovação do usuário, depois implementar. Depois de aprovado, fazer commit e push sem perguntar. Mensagens em
  português, terminando com a linha `Co-Authored-By` da sessão.
- Preferir o caminho simples e remover etapas desnecessárias.
- O README é atualizado no mesmo commit de qualquer mudança no que ele descreve.

## Nada pessoal no código nem na documentação

- Domínio, IPs, nomes de máquinas, contas, e-mails, tokens e IDs **não podem aparecer** no código, nos testes, nos
  READMEs, nas mensagens de commit nem neste arquivo, nem como exemplo. Vão no `.env` (fora do git).
- Exemplos usam marcadores: `<seu-domínio>`, `<domínio>`, `<ip>`.
- Antes de cada commit, conferir com `git grep` os valores do `CLAUDE.local.md`.

## Regras de segurança ao testar

- A máquina atual também roda o Astroverso: **nunca mexer em containers, redes, unidades ou pastas `astroverso-*`
  nem em `~/.astroverso`**. Testes usam nomes `claude-teste-*`, outra rede e outras portas, e removem tudo no fim.
- `sudo` não funciona na sessão do Claude (sem TTY): comandos com `sudo` o usuário roda num terminal (`! <comando>`).
- Não pedir nem aceitar segredos (tokens, senhas, chave da API) no chat: eles entram pelo `.env`.

## Integração opcional com o Astroverso (nunca dependência)

- Endereço `studio.<domínio>` com cadeado: cadastrar como endereço manual no app `network` do Astroverso.
- Avisos no Discord: a API v1 do bot do Astroverso aceita projetos de fora como clientes.
- Futuro app `ia` do Astroverso (ollama, whisper...): o studio pode usar a API dele pela rede como opção, mantendo o
  whisper próprio para funcionar sozinho.

## Armadilhas

- O CDI da GPU (`nvidia-ctk cdi generate`) precisa ser refeito quando o driver da NVIDIA muda. Sem o CDI, o
  `compose.gpu.yaml` impede o container de subir; sem ele, o Whisper roda na CPU.
- As bibliotecas CUDA vêm do pip (`nvidia-cublas-cu12`, `nvidia-cudnn-cu12`) e são achadas pelo `LD_LIBRARY_PATH` do
  `Containerfile`. Trocar a versão do Python da imagem exige atualizar esse caminho.
- SELinux: pastas do repositório montadas em containers usam `:z` (compartilhado). `:Z` dá um rótulo exclusivo e tira
  o acesso dos outros containers que montam a mesma pasta (aconteceu com o banco de teste).
- Estratégias editadas pelo site gravam em `studio/content/`: a mudança só fica salva de verdade depois do commit. Cada
  instância tem o próprio checkout, então a outra só recebe depois de um pull.
- O Postgres e o versitygw escutam na mesma porta dentro e fora do container (`DATABASE_PORT`, `S3_PORT`), para o
  mesmo `.env` servir ao app na rede do compose e às instâncias de fora.
- `podman-compose up --build` não recria um container que já existe com a mesma configuração: use
  `--force-recreate` para pegar a imagem nova.
- O faster-whisper 1.2.1 quebra com o PyAV 19 (`metadata_errors`): o `av` fica fixado abaixo da 19 até sair uma
  versão nova do faster-whisper.
