# Módulos

Cada módulo é uma linha de produção de um tipo de mídia: recebe um pedido, produz e avisa quando terminar. Ele roda
no seu próprio container, com o seu banco, e conversa com o resto do studio só por HTTP.

```
bot ⇄ n8n ⇄ módulo (HTTP) ⇄ postgres (banco do módulo)
       ↖ evento a cada mudança de estado
```

## Contrato

| Item | Como |
|---|---|
| Pasta | `modules/<nome>/` com `Dockerfile`, código, `README.md` e o que mais precisar (`prompts/`, `config/`, `migrations/`, `scripts/`) |
| Serviço | Em `compose.yaml`, um serviço `<nome>` com `build: ./modules/<nome>` e `env_file: .env` |
| API | HTTP na porta 8080 do container, com `Authorization: Bearer <WORKER_TOKEN>` (menos o `/health`) |
| Pedido novo | `POST /jobs` com `url`, `instructions` e `context` (de onde veio: canal e mensagem do Discord) |
| Ações | `POST /jobs/{id}/<ação>` com `{"text": "..."}` (ex.: `approve`, `revise`, `cancel`) |
| Eventos | A cada mudança de estado, `POST` para `http://n8n:5678/webhook/<nome>-events` com o resumo do job |
| Banco | `postgresql://.../<nome>`: o banco é criado por `db/init` (lista `STUDIO_DATABASES` no `compose.yaml`) e as tabelas pelo próprio módulo |
| Arquivos | `./data/<nome>` montado no container; o bot enxerga `./data`, então o caminho de um arquivo para o Discord é `<nome>/...` |
| Discord | Botões com `custom_id` `<nome>:<ação>:<id>`; rodapé das mensagens `<nome> #<id>` (é por ele que uma resposta é ligada ao job) |

## Adicionando um módulo

1. Criar `modules/<nome>/` (o [`cortes`](cortes/) serve de modelo: fila no Postgres, estados, eventos, IA).
2. Adicionar o serviço em `compose.yaml` e `<nome>` em `STUDIO_DATABASES`. Numa instalação existente, criar o
   banco à mão: `STUDIO_DB=postgres sh scripts/psql.sh -c 'CREATE DATABASE "<nome>"'`.
3. Dar ao n8n o endereço do módulo (`<NOME>_URL: http://<nome>:8080` no serviço `n8n`).
4. No n8n: um ramo novo no Switch **Módulo** do fluxo *Studio — entrada do Discord* e um fluxo
   `<nome>-eventos.json` para postar os resultados. Salvar os fluxos em `n8n/workflows/`.
5. Documentar no `README.md` da raiz (tabela de módulos) e no README do módulo.
