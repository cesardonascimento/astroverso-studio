# Astroverso Studio

Estúdio de mídia com IA, em containers (Podman). Você pede pelo Discord, a IA produz e você aprova. Cada tipo de
criação é um **módulo**. Tokens e IDs não ficam no código: vão no `.env`.

| Peça | Para que serve |
|---|---|
| [**bot**](bot/) | **O balcão de pedidos.** Em vez de terminal, você pede e aprova pelo Discord, inclusive pelo celular. O bot do Discord é o **astroverso-discord** (o `astro`), compartilhado com os outros projetos do Astroverso; aqui fica só a ponte, que leva e traz mensagens: recebe links, cliques e respostas e posta roteiros, vídeos e avisos. Só as contas autorizadas no astroverso-discord conseguem usar. |
| [**n8n**](n8n/) | **O fluxo, editável sem programar.** "Quando chegar um pedido, mande ao módulo certo; quando ficar pronto, poste no canal." Essas regras ficam em blocos visuais que você muda pelo navegador, sem mexer no código dos módulos. |
| **postgres** | **A memória.** Um banco por módulo, com cada pedido, suas versões e quanto cada chamada à IA custou. |
| [**módulos**](modules/) | **As linhas de produção.** Cada módulo faz um tipo de mídia, do pedido ao arquivo final, e roda no seu próprio container. |

## Módulos

| Módulo | Para que serve |
|---|---|
| [**cortes**](modules/cortes/) | **Cortes de vídeos longos para o TikTok.** Você manda o link de um vídeo do YouTube (podcast, entrevista, live), a IA escolhe o melhor trecho, você aprova o roteiro e recebe o corte vertical com legendas palavra por palavra. Pedidos de alteração também são feitos pelo Discord. |

Para criar um módulo novo, veja [`modules/README.md`](modules/).

## Como usar

No canal do studio no Discord (ex.: `#studio`):

| Você faz | Resultado |
|---|---|
| Manda um link | Pedido para o módulo padrão (`cortes`) |
| Manda o link com um texto (ex.: `foca na parte do futebol, máximo 40s`) | Pedido seguindo o seu texto |
| Clica nos botões das mensagens do bot | Aprova, refaz, pede alteração, cancela ou tenta de novo |
| Responde a uma mensagem do bot | Pedido de alteração naquele item |

## Instalação

Precisa de Linux (ou WSL) com Podman e `podman-compose`.

```bash
cp .env.example .env              # preencha conforme a seção abaixo
podman login docker.io            # o n8n vem do Docker Hub
podman-compose up -d --build
sh scripts/n8n-deploy.sh          # importa e publica os fluxos no n8n
```

## Respondendo o `.env`

### Base

- **`ASTROVERSO_DISCORD_URL`:** o endereço do astroverso-discord (ex.: `https://discord.<seu-domínio>`). A máquina
  do studio precisa resolver esse nome para o servidor do bot (o AdGuard do homelab faz isso para a rede toda; no
  WSL, confira se o DNS do Windows é o AdGuard).
- **`ASTROVERSO_DISCORD_KEY`:** a chave do cliente `studio`. No assistente do astroverso-discord: **Mostrar a chave
  de um cliente → studio**.
- **`STUDIO_DISCORD_CHANNEL`:** o nome do canal do studio. O bot o cria na categoria do canal principal se ele não
  existir. Padrão: `studio`. Quem pode usar o canal é definido no astroverso-discord (usuários autorizados).
- **`STUDIO_DEFAULT_MODULE`:** o módulo que recebe as mensagens com link. Padrão: `cortes`.
- **`TZ`:** fuso dos agendamentos e logs, no formato `<região>/<cidade>`. Padrão: `UTC`.

### IA

- **`ANTHROPIC_API_KEY`:** a chave da API do Claude, usada pelos módulos. Crie em
  https://console.anthropic.com → API Keys.
- **`LLM_MODEL`:** o modelo do Claude. Padrão: `claude-opus-5-5`. `claude-sonnet-5-5` custa cerca de metade.
- **`LLM_PROVIDER`:** `anthropic` (API, padrão) ou `claude_code` (assinatura do Claude pelo CLI, para testes, com
  `CLAUDE_CODE_OAUTH_TOKEN` gerado por `claude setup-token`).

### Internos

`POSTGRES_PASSWORD`, `WORKER_TOKEN`, `N8N_ENCRYPTION_KEY` e `BOT_API_TOKEN` podem ser quaisquer valores
aleatórios: gere com `openssl rand -hex 32`.

As variáveis de cada módulo estão no README dele.

## Depois de instalar

- **astroverso-discord:** precisa estar instalado, com o cliente `studio` e o **Message Content Intent** ligado (o
  assistente dele avisa). Ao subir, a ponte cria (ou encontra) o canal do studio.
- **n8n:** no primeiro acesso a `http://localhost:5678`, crie a conta de administrador.

## Comandos úteis

```bash
podman-compose ps                        # estado dos serviços
podman logs -f astroverso-studio_bot_1   # a ponte com o Discord
sh scripts/n8n-deploy.sh                 # reaplica os fluxos de n8n/workflows
STUDIO_DB=cortes sh scripts/psql.sh      # banco de um módulo
```

## Estrutura

```
bot/              ponte com o astroverso-discord (compartilhada pelos módulos)
n8n/workflows/    fluxos: entrada do Discord + fluxos de cada módulo
modules/<nome>/   um módulo: código, prompts, presets, banco e scripts
db/init/          cria o banco de cada módulo numa instalação nova
scripts/          utilitários gerais
data/<módulo>/    arquivos gerados por cada módulo (fora do git)
archive/          projetos antigos, só para histórico
```
