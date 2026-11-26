# Astroverso Studio

Estúdio de vídeos com IA. Em refatoração: o fluxo antigo pelo Discord e n8n foi removido e o studio está virando um
app web próprio (pedido, roteiro, aprovação e resultado numa página). Enquanto isso, o módulo
[**cortes**](modules/cortes/) segue funcionando pela API e pelo terminal.

## Instalação

Precisa de Linux com Podman e `podman-compose`.

```bash
cp .env.example .env              # preencha conforme abaixo
podman-compose up -d --build
```

## Respondendo o `.env`

- **`ANTHROPIC_API_KEY`:** a chave da API do Claude. Crie em https://console.anthropic.com → API Keys.
- **`LLM_MODEL`:** o modelo do Claude. Padrão: `claude-opus-5-5`.
- **`POSTGRES_PASSWORD`** e **`WORKER_TOKEN`:** quaisquer valores aleatórios (`openssl rand -hex 32`).
- **`TZ`:** fuso dos logs, no formato `<região>/<cidade>`. Padrão: `UTC`.

As variáveis do módulo estão no README dele.

## Comandos úteis

```bash
podman-compose ps                        # estado dos serviços
STUDIO_DB=cortes sh scripts/psql.sh      # banco do módulo
```
