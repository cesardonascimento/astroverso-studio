"""Bot do Discord do Astroverso Studio: só entrada e saída. A lógica fica no n8n; o trabalho, nos módulos.

Entrada (Discord → n8n, POST {N8N_WEBHOOK_BASE}/discord-in):
  - mensagem no canal com um link          → {"type": "new_request", "module": STUDIO_DEFAULT_MODULE, "url", "instructions"}
  - resposta (reply) a uma mensagem de job → {"type": "action", "module", "action": "revise"|"replan", "job_id", "text"}
  - botões                                 → {"type": "action", "module", "action", "job_id", "text"}
  O n8n responde {"message": "..."}; o bot repassa ao usuário.

Saída (n8n → Discord, POST http://bot:8000/send, Authorization: Bearer BOT_API_TOKEN):
  {"channel_id"?, "reply_to"?, "content"?, "embed"?: {"title","description","color","footer","url"},
   "file_path"?: "<módulo>/...", "buttons"?: [{"label","custom_id","style"}]}

Convenções para os módulos:
  - custom_id dos botões: "<módulo>:<ação>:<id>" (ex.: "cortes:approve:12")
  - rodapé das mensagens: "<módulo> #<id>" (é por ele que uma resposta é ligada ao job)
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from pathlib import Path

import aiohttp
import discord
from aiohttp import web

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s bot: %(message)s")
log = logging.getLogger("bot")

TOKEN = os.environ["DISCORD_BOT_TOKEN"]
CHANNEL_ID = int(os.environ["DISCORD_CHANNEL_ID"])
ALLOWED = {int(x) for x in os.environ.get("DISCORD_ALLOWED_USER_IDS", "").replace(" ", "").split(",") if x}
DEFAULT_MODULE = os.environ.get("STUDIO_DEFAULT_MODULE", "cortes")
N8N = os.environ.get("N8N_WEBHOOK_BASE", "http://n8n:5678/webhook").rstrip("/")
API_TOKEN = os.environ["BOT_API_TOKEN"]
MEDIA = Path(os.environ.get("MEDIA_DIR", "/data"))

URL_RE = re.compile(r"https?://\S+")
REF_RE = re.compile(r"\b([A-Za-z][A-Za-z0-9_-]*) #(\d+)")
# nomes antigos (mensagens já postadas antes dos módulos)
ALIASES = {"cut": "cortes", "corte": "cortes"}
STYLES = {"primary": discord.ButtonStyle.primary, "success": discord.ButtonStyle.success,
          "danger": discord.ButtonStyle.danger, "secondary": discord.ButtonStyle.secondary}
ACTION_LABEL = {"replan": "Refazer o roteiro", "revise": "Pedir alteração"}

intents = discord.Intents.default()
intents.message_content = True  # precisa estar ligado no Developer Portal
client = discord.Client(intents=intents)


def allowed(user: discord.abc.User) -> bool:
    return not ALLOWED or user.id in ALLOWED


def module_name(name: str) -> str:
    name = name.lower()
    return ALIASES.get(name, name)


async def to_n8n(payload: dict) -> str:
    """Envia ao n8n e devolve a mensagem de resposta (ou um erro legível)."""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as s:
            async with s.post(f"{N8N}/discord-in", json=payload) as r:
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


def job_ref(msg: discord.Message) -> tuple[str, int] | None:
    """(módulo, id) de uma mensagem do bot, pelo rodapé "<módulo> #<id>"."""
    texts = []
    for e in msg.embeds:
        texts += [e.footer.text if e.footer else "", e.title or ""]
    texts.append(msg.content or "")
    for t in texts:
        if (m := REF_RE.search(t)):
            return module_name(m.group(1)), int(m.group(2))
    return None


# ---------------------------------------------------------------- entrada
@client.event
async def on_ready():
    log.info("conectado como %s; canal %s; módulo padrão %s", client.user, CHANNEL_ID, DEFAULT_MODULE)


@client.event
async def on_message(msg: discord.Message):
    if msg.author.bot or msg.channel.id != CHANNEL_ID or not allowed(msg.author):
        return
    ctx = {"channel_id": str(msg.channel.id), "message_id": str(msg.id),
           "user_id": str(msg.author.id), "user": msg.author.display_name}

    # resposta a uma mensagem do bot sobre um job → pedido de alteração
    if msg.reference and msg.reference.message_id:
        try:
            ref = msg.reference.resolved or await msg.channel.fetch_message(msg.reference.message_id)
        except discord.HTTPException:
            ref = None
        if isinstance(ref, discord.Message) and ref.author == client.user and (r := job_ref(ref)):
            module, jid = r
            action = "revise" if ref.attachments else "replan"
            await msg.add_reaction("🔁")
            reply = await to_n8n({"type": "action", "module": module, "action": action, "job_id": jid,
                                  "text": msg.content, "discord": ctx})
            await msg.reply(reply, mention_author=False)
            return

    m = URL_RE.search(msg.content or "")
    if not m:
        return
    url = m.group(0).rstrip(">)")
    instructions = (msg.content[:m.start()] + msg.content[m.end():]).strip()
    await msg.add_reaction("👀")
    reply = await to_n8n({"type": "new_request", "module": DEFAULT_MODULE, "url": url,
                          "instructions": instructions, "discord": ctx})
    await msg.reply(reply, mention_author=False)


class TextModal(discord.ui.Modal):
    def __init__(self, module: str, action: str, job_id: int):
        super().__init__(title=f"{ACTION_LABEL[action]} — {module} #{job_id}"[:45])
        self.module, self.action, self.job_id = module, action, job_id
        self.text = discord.ui.TextInput(
            label="O que você quer?", style=discord.TextStyle.paragraph, max_length=1500,
            placeholder="ex.: começa uma frase antes, tira a parte do patrocínio, legenda maior...")
        self.add_item(self.text)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        reply = await to_n8n({"type": "action", "module": self.module, "action": self.action,
                              "job_id": self.job_id, "text": str(self.text.value), "discord": _ictx(interaction)})
        await interaction.followup.send(f"{interaction.user.mention}: {self.text.value}\n{reply}")


def _ictx(i: discord.Interaction) -> dict:
    return {"channel_id": str(i.channel_id), "user_id": str(i.user.id), "user": i.user.display_name,
            "message_id": str(i.message.id) if i.message else None}


@client.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type != discord.InteractionType.component:
        return
    parts = ((interaction.data or {}).get("custom_id") or "").split(":")
    if len(parts) != 3 or not parts[2].isdigit():
        return  # botões de outros bots/projetos (ex.: "astro|...") passam direto
    if not allowed(interaction.user):
        await interaction.response.send_message("sem permissão", ephemeral=True)
        return
    module, action, jid = module_name(parts[0]), parts[1], int(parts[2])
    if action in ACTION_LABEL:
        await interaction.response.send_modal(TextModal(module, action, jid))
        return
    await interaction.response.defer(thinking=True)
    reply = await to_n8n({"type": "action", "module": module, "action": action, "job_id": jid, "text": "",
                          "discord": _ictx(interaction)})
    await interaction.followup.send(f"{interaction.user.mention}: {reply}")


# ---------------------------------------------------------------- saída (API para o n8n)
def _view(buttons: list[dict]) -> discord.ui.View | None:
    if not buttons:
        return None
    v = discord.ui.View(timeout=None)
    for b in buttons[:5]:
        v.add_item(discord.ui.Button(label=b["label"][:80], custom_id=b["custom_id"],
                                     style=STYLES.get(b.get("style", "secondary"), discord.ButtonStyle.secondary)))
    return v


async def api_send(request: web.Request) -> web.Response:
    if request.headers.get("Authorization") != f"Bearer {API_TOKEN}":
        return web.json_response({"error": "unauthorized"}, status=401)
    body = await request.json()
    channel = client.get_channel(int(body.get("channel_id") or CHANNEL_ID)) or \
        await client.fetch_channel(int(body.get("channel_id") or CHANNEL_ID))
    kwargs: dict = {"content": (body.get("content") or None) and body["content"][:2000]}
    if (e := body.get("embed")):
        emb = discord.Embed(title=(e.get("title") or "")[:256] or None, description=(e.get("description") or "")[:4000],
                            color=int(e.get("color", 0x5865F2)), url=e.get("url") or None)
        if e.get("footer"):
            emb.set_footer(text=e["footer"][:2048])
        kwargs["embed"] = emb
    if (fp := body.get("file_path")):
        path = (MEDIA / fp).resolve()
        if MEDIA.resolve() not in path.parents or not path.exists():
            return web.json_response({"error": f"arquivo inválido: {fp}"}, status=400)
        kwargs["file"] = discord.File(path, filename=body.get("file_name") or path.name)
    if (v := _view(body.get("buttons") or [])):
        kwargs["view"] = v
    if body.get("reply_to"):
        try:
            ref = await channel.fetch_message(int(body["reply_to"]))
            msg = await ref.reply(mention_author=False, **kwargs)
        except discord.HTTPException:
            msg = await channel.send(**kwargs)
    else:
        msg = await channel.send(**kwargs)
    return web.json_response({"message_id": str(msg.id)})


async def api_health(_: web.Request) -> web.Response:
    return web.json_response({"ok": client.is_ready()})


async def main():
    app = web.Application(client_max_size=2 * 1024 * 1024)
    app.add_routes([web.post("/send", api_send), web.get("/health", api_health)])
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", 8000).start()
    log.info("API do bot em :8000")
    async with client:
        await client.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
