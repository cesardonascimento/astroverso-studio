# astroverso-studio

Cortes de vídeos do YouTube para o TikTok, pedidos e aprovados pelo Discord. Você manda o link, a IA escolhe o
melhor trecho, você aprova o roteiro e recebe o vídeo vertical com legendas. Tokens e IDs não ficam no código:
vão no `.env`.

| Peça | Para que serve |
|---|---|
| [**worker**](worker/) | **A linha de produção.** Fazer um corte à mão exige baixar o vídeo, ler a transcrição, achar o trecho bom, cortar, enquadrar na vertical e legendar palavra por palavra. O worker faz tudo isso sozinho: usa a legenda que o YouTube já fornece (ou transcreve, se não houver), pede ao Claude o melhor trecho e monta o vídeo com o FFmpeg. Cada corte passa por etapas com estado salvo: se algo cair no meio, ele continua de onde parou, sem duplicar. |
| [**bot**](bot/) | **A conversa pelo Discord.** Em vez de terminal, você pede e aprova os cortes num canal do Discord, inclusive pelo celular. O bot só leva e traz mensagens: recebe o link e os cliques nos botões e posta roteiros, vídeos e avisos. Só as contas autorizadas conseguem pedir. |
| [**n8n**](n8n/) | **O fluxo, editável sem programar.** "Quando chegar um link, crie o corte; quando o roteiro ficar pronto, peça aprovação; quando o vídeo ficar pronto, poste." Essas regras ficam no n8n, em blocos visuais que você muda pelo navegador, sem mexer no código do worker. |
| **postgres** | **A memória.** Guarda cada corte, suas versões (com o pedido que gerou cada uma), as transcrições e quanto cada chamada à IA custou. |

## Como usar

No canal do studio no Discord (ex.: `#studio`):

| Você faz | Resultado |
|---|---|
| Manda um link | Cria o corte. O bot responde com o número dele |
| Manda o link com um texto (ex.: `foca na parte do futebol, máximo 40s`) | Cria o corte seguindo o seu pedido |
| **Aprovar**, na prévia do roteiro | Gera o vídeo |
| **Refazer roteiro**, ou responde à prévia com o que quer | Novo roteiro com o seu pedido |
| **Pedir alteração**, ou responde à mensagem do vídeo | Nova versão do vídeo com a alteração |
| **Cancelar** / **Tentar de novo** | Cancela o corte / retoma um corte que falhou |

O vídeo no Discord é uma prévia leve (o Discord limita o envio a 10 MB). O arquivo final, em 1080x1920, fica em
`data/media/jobs/<corte>/render_v<versão>/final.mp4`. Todas as versões ficam guardadas.

## Instalação

Precisa de Linux (ou WSL) com Podman e `podman-compose`.

```bash
cp .env.example .env              # preencha conforme a seção abaixo
podman login docker.io            # o n8n vem do Docker Hub
podman-compose up -d --build
sh scripts/n8n-deploy.sh          # importa e publica os fluxos no n8n
```

## Respondendo o `.env`

### Obrigatórios

- **`ANTHROPIC_API_KEY`:** a chave da API do Claude, que escolhe os trechos e aplica as alterações. Crie em
  https://console.anthropic.com → API Keys. Cada corte custa alguns centavos de dólar.
- **`DISCORD_BOT_TOKEN`:** o token do bot que vai conversar no canal. No Discord Developer Portal → sua
  aplicação → Bot → Reset Token.
- **`DISCORD_CHANNEL_ID`:** o canal onde você pede os cortes. O bot ignora os outros canais. Para copiar o ID,
  ligue o Modo Desenvolvedor do Discord e clique com o botão direito no canal.
- **`DISCORD_ALLOWED_USER_IDS`:** quem pode pedir cortes, IDs separados por vírgula. Vazio libera para todos que
  escrevem no canal. Recomendado: só o seu.

### Opcionais

- **`LLM_MODEL`:** o modelo do Claude. Padrão: `claude-opus-5-5`. `claude-sonnet-5-5` custa cerca de metade.
- **`CUT_MAX_DURATION_S`:** duração máxima de um corte, em segundos. Padrão: `75`. Um pedido no próprio link
  ("máximo 40s") vale mais.
- **`CUT_LAYOUT`:** como o vídeo horizontal vira vertical. Padrão: `auto` (ver [worker](worker/#layouts)).
- **`WHISPER_MODEL`:** o modelo de transcrição local, usado só quando o YouTube não tem legenda. Padrão: `small`.
  Maiores (`medium`, `large-v3`) acertam mais e demoram mais.
- **`YOUTUBE_COOKIES_FILE`:** cookies do navegador, se o YouTube pedir login. Vazio na maioria dos casos.
- **`LLM_PROVIDER`:** `anthropic` (API, padrão) ou `claude_code` (assinatura do Claude, pelo CLI; para testes,
  com `CLAUDE_CODE_OAUTH_TOKEN` gerado por `claude setup-token`).

As senhas e tokens internos (`POSTGRES_PASSWORD`, `WORKER_TOKEN`, `N8N_ENCRYPTION_KEY`, `BOT_API_TOKEN`) podem
ser quaisquer valores aleatórios: gere com `openssl rand -hex 32`.

## Personalizar sem programar

| O quê | Onde |
|---|---|
| Como a IA escolhe o corte | `prompts/clip_plan.md` |
| Como a IA aplica alterações | `prompts/clip_revise.md` |
| Estilos de legenda, duração e layout padrão | `config/presets.json` (vale no próximo vídeo) |
| O fluxo entre Discord e worker | n8n, em `http://localhost:5678` |

## Depois de instalar

- **Discord Developer Portal → Bot:** ligue **Message Content Intent**. Sem ele, o bot não lê o link das
  mensagens e não conecta.
- **Convite do bot:** o bot precisa ver o canal, enviar mensagens, anexar arquivos e ler o histórico.
- **n8n:** no primeiro acesso a `http://localhost:5678`, crie a conta de administrador.

## Comandos úteis

```bash
podman-compose ps                         # estado dos serviços
podman logs -f astroverso-studio_worker_1      # o que o worker está fazendo
sh scripts/api.sh GET /jobs               # últimos cortes
sh scripts/api.sh GET /jobs/<corte>/preview
sh scripts/cut.sh "<link>" auto           # corte direto pelo terminal, sem aprovação
```

## Estrutura

```
worker/         linha de produção (ver worker/README.md)
bot/            bot do Discord (ver bot/README.md)
n8n/workflows/  fluxos do n8n (ver n8n/README.md)
prompts/        instruções da IA
config/         presets editáveis
db/migrations/  banco
scripts/        utilitários de terminal
data/media/     vídeos baixados e gerados
```
