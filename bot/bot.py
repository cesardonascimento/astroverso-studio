"""Ponte do Astroverso Studio com o Discord. O bot em si é o astroverso-discord (o `astro`), compartilhado com
outros projetos; esta ponte é o cliente `studio` dele. A lógica fica no n8n; o trabalho, nos módulos.

Entrada (astroverso-discord → ponte → n8n, POST {N8N_WEBHOOK_BASE}/discord-in):
  - mensagem no canal com um link          → {"type": "new_request", "module": STUDIO_DEFAULT_MODULE, "url", "instructions"}
  - resposta (reply) a uma mensagem de job → {"type": "action", "module", "action": "revise"|"replan", "job_id", "text"}
  - botões                                 → {"type": "action", "module", "action", "job_id", "text"}
  O n8n responde {"message": "..."}; a ponte devolve ao astroverso-discord, que responde no canal.

Saída (n8n → ponte → astroverso-discord, POST http://bot:8000/send, Authorization: Bearer BOT_API_TOKEN):
  {"channel_id"?, "reply_to"?, "content"?, "embed"?: {"title","description","color","footer","url"},
   "file_path"?: "<módulo>/...", "file_name"?, "buttons"?: [{"label","custom_id","style"}]}

Convenções para os módulos:
  - custom_id dos botões: "<módulo>:<ação>:<id>" (ex.: "cortes:approve:12")
  - rodapé das mensagens: "<módulo> #<id>" (é por ele que uma resposta é ligada ao job)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from pathlib import Path

import aiohttp
from aiohttp import web

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s bot: %(message)s")
log = logging.getLogger("bot")

DISCORD = os.environ["ASTROVERSO_DISCORD_URL"].rstrip("/")
DISCORD_KEY = os.environ["ASTROVERSO_DISCORD_KEY"]
CHANNEL = os.environ.get("STUDIO_DISCORD_CHANNEL", "studio")
DEFAULT_MODULE = os.environ.get("STUDIO_DEFAULT_MODULE", "cortes")
N8N = os.environ.get("N8N_WEBHOOK_BASE", "http://n8n:5678/webhook").rstrip("/")
API_TOKEN = os.environ["BOT_API_TOKEN"]
MEDIA = Path(os.environ.get("MEDIA_DIR", "/data"))
PUBLISH_EVERY = 300

URL_RE = re.compile(r"https?://\S+")
REF_RE = re.compile(r"\b([A-Za-z][A-Za-z0-9_-]*) #(\d+)")
# nomes antigos (mensagens já postadas antes dos módulos)
ALIASES = {"cut": "cortes", "corte": "cortes"}
STYLES = {"primary", "success", "danger", "secondary"}
# o que o studio declara ao astroverso-discord: o canal que ele escuta e os botões que são dele
# (Refazer e Pedir alteração abrem uma caixa de texto antes de virar evento)
MANIFEST = {
    "canais": [{"nome": CHANNEL, "escrita": True, "escuta": True}],
    "botoes": [{
        "padrao": r"^[A-Za-z][A-Za-z0-9_-]*:[a-z_]+:\d+$",
        "texto": {"padrao": r"^[A-Za-z][A-Za-z0-9_-]*:(replan|revise):\d+$", "titulo": "Pedido ao studio",
                  "rotulo": "O que você quer?",
                  "dica": "ex.: começa uma frase antes, tira a parte do patrocínio, legenda maior..."},
    }],
}

state = {"channel_id": None, "connected": False}
session: aiohttp.ClientSession | None = None


def module_name(name: str) -> str:
    name = name.lower()
    return ALIASES.get(name, name)


async def discord_call(method: str, path: str, **kwargs) -> dict:
    """Chama a API do astroverso-discord com a chave do cliente studio."""
    async with session.request(method, f"{DISCORD}{path}", headers={"Authorization": f"Bearer {DISCORD_KEY}"},
                               **kwargs) as r:
        raw = await r.text()
        if r.status >= 300:
            raise RuntimeError(f"astroverso-discord respondeu {r.status}: {raw[:200]}")
        return json.loads(raw) if raw else {}


async def to_n8n(payload: dict) -> str:
    """Envia ao n8n e devolve a mensagem de resposta (ou um erro legível)."""
    try:
        async with session.post(f"{N8N}/discord-in", json=payload, timeout=aiohttp.ClientTimeout(total=60)) as r:
            if r.status >= 300:
                return f"⚠️ n8n respondeu {r.status}"
            try:
                data = await r.json(content_type=None)
            except Exception:  # noqa: BLE001
                return "✅ recebido"
            if isinstance(data, list):
                data = data[0] if data else {}
            return str(data.get("message") or "✅ recebido")
    except Exception as e:  # noqa: BLE001
        log.exception("falha ao falar com o n8n")
        return f"⚠️ não consegui falar com o n8n ({type(e).__name__})"


def job_ref(ref: dict) -> tuple[str, int] | None:
    """(módulo, id) de uma mensagem do bot, pelo rodapé "<módulo> #<id>"."""
    texts = []
    for q in ref.get("quadros") or []:
        texts += [q.get("rodape") or "", q.get("titulo") or ""]
    texts.append(ref.get("texto") or "")
    for t in texts:
        if (m := REF_RE.search(t)):
            return module_name(m.group(1)), int(m.group(2))
    return None


async def answer(event_id: str, text: str) -> None:
    await discord_call("POST", f"/v1/eventos/{event_id}/resposta", json={"texto": text[:2000]})


async def react(event: dict, emoji: str) -> None:
    try:
        await discord_call("POST", "/v1/reacoes",
                           json={"canal_id": event["canal_id"], "mensagem_id": event["mensagem_id"], "emoji": emoji})
    except Exception as e:  # noqa: BLE001
        log.warning("reação recusada: %s", e)


# ---------------------------------------------------------------- entrada
async def on_message(event: dict) -> None:
    user = event.get("usuario") or {}
    ctx = {"channel_id": event.get("canal_id"), "message_id": event.get("mensagem_id"),
           "user_id": user.get("id"), "user": user.get("exibicao") or user.get("nome")}
    text = event.get("texto") or ""

    # resposta a uma mensagem do bot sobre um job → pedido de alteração
    ref = event.get("responde_a")
    if ref and ref.get("do_bot") and (r := job_ref(ref)):
        module, jid = r
        action = "revise" if ref.get("anexos") else "replan"
        await react(event, "🔁")
        reply = await to_n8n({"type": "action", "module": module, "action": action, "job_id": jid,
                              "text": text, "discord": ctx})
        await answer(event["id"], reply)
        return

    m = URL_RE.search(text)
    if not m:
        return
    url = m.group(0).rstrip(">)")
    instructions = (text[:m.start()] + text[m.end():]).strip()
    await react(event, "👀")
    reply = await to_n8n({"type": "new_request", "module": DEFAULT_MODULE, "url": url,
                          "instructions": instructions, "discord": ctx})
    await answer(event["id"], reply)


async def on_button(event: dict) -> None:
    parts = (event.get("custom_id") or "").split(":")
    if len(parts) != 3 or not parts[2].isdigit():
        return
    user = event.get("usuario") or {}
    ctx = {"channel_id": event.get("canal_id"), "user_id": user.get("id"),
           "user": user.get("exibicao") or user.get("nome"), "message_id": event.get("mensagem_id")}
    module, action, jid = module_name(parts[0]), parts[1], int(parts[2])
    text = event.get("texto") or ""
    reply = await to_n8n({"type": "action", "module": module, "action": action, "job_id": jid, "text": text,
                          "discord": ctx})
    mention = f"<@{user.get('id')}>"
    await answer(event["id"], f"{mention}: {text}\n{reply}" if text else f"{mention}: {reply}")


async def handle(event: dict) -> None:
    try:
        if event.get("tipo") == "mensagem":
            await on_message(event)
        elif event.get("tipo") == "botao":
            await on_button(event)
    except Exception:  # noqa: BLE001
        log.exception("falha ao tratar o evento %s", event.get("id"))


async def publish() -> None:
    data = await discord_call("PUT", "/v1/cliente", json=MANIFEST)
    state["channel_id"] = (data.get("canais") or {}).get(CHANNEL)
    state["connected"] = True
    log.info("conectado ao astroverso-discord em %s; canal #%s (%s); módulo padrão %s",
             DISCORD, CHANNEL, state["channel_id"] or "sem permissão para criar", DEFAULT_MODULE)


async def events_loop() -> None:
    """Busca os eventos do cliente studio (espera de até 25s) e republica o manifesto a cada 5 min."""
    loop = asyncio.get_running_loop()
    last = None
    while True:
        try:
            if last is None or loop.time() - last >= PUBLISH_EVERY:
                await publish()
                last = loop.time()
            data = await discord_call("GET", "/v1/eventos?espera=25", timeout=aiohttp.ClientTimeout(total=40))
            state["connected"] = True
            for event in data.get("eventos") or []:
                asyncio.create_task(handle(event))
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            if state["connected"] or last is None:
                log.warning("sem conexão com o astroverso-discord (%s): tento de novo a cada 10s", e)
            state["connected"] = False
            last = None
            await asyncio.sleep(10)


# ---------------------------------------------------------------- saída (API para o n8n)
def translate(body: dict) -> dict:
    """Formato do n8n (/send) → formato do astroverso-discord (/v1/mensagens)."""
    out: dict = {"texto": (body.get("content") or "")[:2000]}
    if body.get("channel_id"):
        out["canal_id"] = str(body["channel_id"])
    else:
        out["canal"] = CHANNEL
    if body.get("reply_to"):
        out["responde_a"] = str(body["reply_to"])
    if (e := body.get("embed")):
        out["quadro"] = {"titulo": e.get("title"), "descricao": e.get("description"),
                         "cor": int(e.get("color", 0x5865F2)), "rodape": e.get("footer"), "url": e.get("url")}
    if (buttons := body.get("buttons")):
        out["botoes"] = [{"rotulo": b["label"], "custom_id": b["custom_id"],
                          "estilo": b.get("style") if b.get("style") in STYLES else "secondary"} for b in buttons[:5]]
    return out


async def api_send(request: web.Request) -> web.Response:
    if request.headers.get("Authorization") != f"Bearer {API_TOKEN}":
        return web.json_response({"error": "unauthorized"}, status=401)
    body = await request.json()
    message = translate(body)
    try:
        if (fp := body.get("file_path")):
            path = (MEDIA / fp).resolve()
            if MEDIA.resolve() not in path.parents or not path.exists():
                return web.json_response({"error": f"arquivo inválido: {fp}"}, status=400)
            message["arquivo_nome"] = body.get("file_name") or path.name
            with path.open("rb") as f:
                form = aiohttp.FormData()
                form.add_field("dados", json.dumps(message, ensure_ascii=False), content_type="application/json")
                form.add_field("arquivo", f, filename=message["arquivo_nome"])
                data = await discord_call("POST", "/v1/mensagens", data=form)
        else:
            data = await discord_call("POST", "/v1/mensagens", json=message)
    except Exception as e:  # noqa: BLE001
        log.warning("mensagem não enviada: %s", e)
        return web.json_response({"error": str(e)}, status=502)
    return web.json_response({"message_id": data.get("mensagem_id")})


async def api_health(_: web.Request) -> web.Response:
    return web.json_response({"ok": state["connected"]})


async def main():
    global session
    session = aiohttp.ClientSession()
    app = web.Application(client_max_size=2 * 1024 * 1024)
    app.add_routes([web.post("/send", api_send), web.get("/health", api_health)])
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", 8000).start()
    log.info("API da ponte em :8000")
    try:
        await events_loop()
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(main())
