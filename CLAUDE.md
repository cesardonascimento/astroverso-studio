# CLAUDE.md

Regras para desenvolver o Astroverso Studio. O contexto da instalação atual (máquina, GPU, rede) fica em
`CLAUDE.local.md`, fora do git.

## Situação

O código atual é uma **prova de conceito**: cortes de vídeos do YouTube para o TikTok, pedidos e aprovados pelo
Discord. Ele foi feito para rodar num PC separado e conversar com o bot do Astroverso, por isso tem a ponte com o
astroverso-discord (`bot/`), o n8n como orquestrador e o Postgres.

Decidido em 26/11/2026: o studio é um **projeto próprio, independente do Astroverso**, que roda em qualquer máquina
com GPU (inclusive uma com hardware melhor, no futuro). Ele será refatorado; o código atual serve só de referência e
pode ser reescrito à vontade.

### Direção da refatoração

- **Interface web própria** no lugar do Discord: novo pedido (link + instruções), acompanhar o progresso, ler e
  editar o roteiro, aprovar, assistir e baixar o corte, histórico.
- **Sem n8n e sem Discord:** o fluxo (pedido → roteiro → aprovação → render) fica dentro do próprio app. Sai a pasta
  `bot/` e `n8n/`.
- **Banco mais simples:** SQLite no lugar do Postgres, a menos que a arquitetura mostre um motivo para manter.
- **Whisper na GPU NVIDIA** (faster-whisper com CUDA). No Podman, a GPU entra pelo `nvidia-container-toolkit` e
  CDI (`nvidia-ctk cdi generate`, `--device nvidia.com/gpu=all`); o CDI precisa ser refeito quando o driver muda.
  Com 4 GB de VRAM: `medium` ou `large-v3` em `int8_float16`. Sem GPU, cai para CPU (`int8`).
- **Sem o provedor `claude_code`** (Claude Code CLI na imagem): só a API da Anthropic.
- O `archive/tendencias` continua só como histórico.

### Em aberto (decidir na primeira etapa de arquitetura)

- Stack do backend (manter FastAPI?) e da interface (HTML/JS puro ou um front com build).
- Login na página.
- Onde ficam os vídeos gerados e quando são limpos.
- Forma de rodar: `podman-compose` como hoje ou outra.

### Integração opcional com o Astroverso (nunca dependência)

- Endereço `studio.<domínio>` com cadeado: cadastrar como endereço manual no app `network` do Astroverso.
- Avisos no Discord: a API v1 do bot do Astroverso aceita projetos de fora como clientes.
- Futuro app `ia` do Astroverso (ollama, whisper...): o studio pode usar a API dele pela rede como opção, mantendo o
  whisper próprio para funcionar sozinho.

## Como trabalhar

- Responder sempre em **português do Brasil**, de forma direta.
- **Micro commits.** Um pedaço pequeno por vez: primeiro descrever a arquitetura daquele pedaço e esperar a
  aprovação do usuário, depois implementar. Depois de aprovado, fazer commit e push sem perguntar. Mensagens em
  português, terminando com a linha `Co-Authored-By` da sessão.
- Preferir o caminho simples e remover etapas desnecessárias.
- O README é atualizado no mesmo commit de qualquer mudança no que ele descreve.

## Nada pessoal no código nem na documentação

- Domínio, IPs, nomes de máquinas, contas, e-mails, tokens e IDs do Discord **não podem aparecer** no código, nos
  testes, nos READMEs, nas mensagens de commit nem neste arquivo, nem como exemplo. Vão no `.env` (fora do git).
- Exemplos usam marcadores: `<seu-domínio>`, `<domínio>`, `<ip>`.
- Antes de cada commit, conferir com `git grep` os valores do `CLAUDE.local.md`.

## Regras de segurança ao testar

- A máquina atual também roda o Astroverso: **nunca mexer em containers, redes, unidades ou pastas `astroverso-*`
  nem em `~/.astroverso`**. Testes usam nomes `claude-teste-*`, outra rede e outras portas, e removem tudo no fim.
- `sudo` não funciona na sessão do Claude (sem TTY): comandos com `sudo` o usuário roda num terminal (`! <comando>`).
- Não pedir nem aceitar segredos (tokens, senhas, chave da API) no chat: eles entram pelo `.env`.
