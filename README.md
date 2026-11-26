# Astroverso Studio

## O que é

Estúdio de vídeos com IA, num app web próprio. Você escolhe um algoritmo de geração, as redes de destino e a
estratégia de cada uma; a IA produz o roteiro, você aprova ou edita, e recebe o vídeo pronto.

- **Guarda-chuva:** três peças num repositório: o app (`studio`), o banco (Postgres) e o armazenamento de vídeos (S3).
  Sobem juntas numa máquina ou separadas, com o banco e o S3 num PC que faz papel de NAS.
- **Várias instâncias, mesmos dados:** duas ou mais máquinas com o app apontam para o mesmo banco e o mesmo S3. Cada
  uma processa as próprias gerações e todas veem tudo.
- **Vídeos como arquivos comuns:** o S3 (versitygw) grava cada objeto como arquivo numa pasta do disco, fácil de
  navegar e de copiar para backup.

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
| `S3_*` | Endereço, porta, bucket, chaves e pasta de dados do S3 |
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
- **`modules/cortes`:** prova de conceito antiga, só como referência.

### Camadas do app

- **`app/config.py`:** o único lugar que lê variáveis de ambiente. Toda variável nova entra também no `.env.example`.

### Testes

```bash
cd studio && podman build --target test -t studio-test .
cd .. && podman run --rm -v .:/repo:Z -w /repo/studio studio-test python -m pytest
```

Os testes conferem, entre outras coisas, que o `.env.example` lista todas as variáveis usadas pelo app e pelo
`compose.yaml`.
