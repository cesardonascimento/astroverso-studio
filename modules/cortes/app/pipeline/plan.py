"""Análise da transcrição → plano do corte. Três modos:
  initial  — primeiro plano (usa as instruções enviadas junto com o link)
  replan   — refazer o roteiro antes de aprovar (novo plano, com o pedido)
  revision — alterações pedidas DEPOIS do vídeo pronto (parte do plano atual e muda só o pedido)
"""
from __future__ import annotations

import json

from ..config import presets, settings
from ..llm import llm, load_prompt
from ..render.effects import available as available_effects
from ..schemas import ClipPlan
from .source import transcript_lines

PAD_START, PAD_END = 0.10, 0.25  # respiro nas bordas dos segmentos (s)


def fmt_ts(t: float) -> str:
    m, s = divmod(max(t, 0), 60)
    h, m = divmod(int(m), 60)
    return f"{h}:{m:02d}:{s:04.1f}" if h else f"{m}:{s:04.1f}"


def snap_segments(segments: list[dict], words: list[dict], source_duration: float) -> list[dict]:
    """Ajusta os segmentos às fronteiras reais das palavras e junta o texto exato de cada um."""
    out = []
    for seg in segments:
        # o LLM usa o início exato das linhas: tolerância pequena para não puxar palavra da frase anterior
        inside = [w for w in words if w["s"] >= seg["start"] - 0.05 and w["s"] < seg["end"] - 0.05]
        if not inside:
            continue
        start = max(0.0, inside[0]["s"] - PAD_START)
        end = min(source_duration, inside[-1]["e"] + PAD_END)
        out.append({"start": round(start, 3), "end": round(end, 3), "purpose": seg.get("purpose", ""),
                    # tempos exatos da 1ª e última palavra (sem respiro): usados para revisões
                    "text_start": inside[0]["s"], "text_end": inside[-1]["e"],
                    "text": " ".join(w["w"] for w in inside), "words": len(inside)})
    for a, b in zip(out, out[1:]):  # remove sobreposição
        if a["start"] < b["start"] < a["end"]:
            a["end"] = b["start"]
    return out


def keep_or_snap(new: list[dict], old: list[dict], words: list[dict], src_dur: float) -> list[dict]:
    """Numa revisão, segmento que voltou (quase) igual a um anterior é copiado tal e qual — assim
    revisões sucessivas não vão "andando" as bordas. Os demais são ajustados às palavras normalmente."""
    out = []
    for sg in new:
        same = next((o for o in old
                     if abs(sg["start"] - o.get("text_start", o["start"])) < 0.4
                     and abs(sg["end"] - o.get("text_end", o["end"])) < 0.4), None)
        if same:
            out.append({**same, "purpose": sg.get("purpose") or same.get("purpose", "")})
        else:
            out += snap_segments([sg], words, src_dur)
    return out


def _context_block(job: dict, max_dur: int) -> str:
    p = presets()
    subs = {k: v.get("description", "") for k, v in p.get("subtitles", {}).items()}
    effects = available_effects()
    return (
        f"Vídeo: {job['source_title']} — canal {job['source_channel']}\n"
        f"Duração máxima do corte: {max_dur} segundos.\n"
        f"Presets de legenda disponíveis: {json.dumps(subs, ensure_ascii=False)}\n"
        "Layouts: auto (automático), crop (tela cheia cortando as laterais), "
        "fit_blur (vídeo inteiro com fundo desfocado), split (duas regiões empilhadas, ex.: react).\n"
        f"Efeitos disponíveis: {json.dumps(effects, ensure_ascii=False) if effects else '(nenhum ainda)'}\n"
    )


def _transcript_block(words: list[dict]) -> str:
    return "TRANSCRIÇÃO ([início em segundos] texto):\n" + "\n".join(
        f"[{ln['s']:.1f}] {ln['text']}" for ln in transcript_lines(words))


def make_plan(job: dict, mode: str = "initial", request: str | None = None) -> dict:
    s = settings()
    opts = job["options"] or {}
    max_dur = int(opts.get("max_duration_s") or presets().get("defaults", {}).get("max_duration_s")
                  or s.cut_max_duration_s)
    words = job["transcript"]
    ctx_txt = _context_block(job, max_dur)

    if mode == "revision":
        version, system = load_prompt("clip_revise")
        current = {k: v for k, v in (job["plan"] or {}).items()
                   if k in ("title", "hook_text", "caption", "hashtags", "edits", "render")}
        # segmentos com os tempos exatos das palavras (sem o respiro), para não puxar a palavra seguinte
        current["segments"] = [
            {"start": sg.get("text_start", sg["start"]), "end": sg.get("text_end", sg["end"]),
             "purpose": sg.get("purpose", ""), "text": sg.get("text", "")}
            for sg in (job["plan"] or {}).get("segments", [])]
        user = (ctx_txt + f"\nPLANO ATUAL:\n{json.dumps(current, ensure_ascii=False)}\n\n"
                f"PEDIDO DE ALTERAÇÃO DO EDITOR:\n{request}\n\n" + _transcript_block(words))
    else:
        version, system = load_prompt("clip_plan")
        instr = "\n".join(x for x in (job.get("instructions"), request) if x)
        user = (ctx_txt + (f"\nINSTRUÇÕES DO EDITOR:\n{instr}\n" if instr else "")
                + ("\n(É um novo pedido para um corte que o editor não aprovou. Proponha algo diferente "
                   "seguindo o pedido.)\n" if mode == "replan" else "")
                + "\n" + _transcript_block(words))

    plan = llm().structured(step=f"clip_{mode}", system=system, user=user, output=ClipPlan,
                            ctx={"job_id": job["id"]}).model_dump()
    src_dur = float(job["source_duration_s"] or 1e9)
    if mode == "revision":
        plan["segments"] = keep_or_snap(plan["segments"], (job["plan"] or {}).get("segments", []), words, src_dur)
    else:
        plan["segments"] = snap_segments(plan["segments"], words, src_dur)
    if not plan["segments"]:
        raise RuntimeError("o plano não tem segmentos válidos")
    plan["duration_s"] = round(sum(x["end"] - x["start"] for x in plan["segments"]), 2)
    plan["prompt_version"] = version
    plan["model"] = s.llm_model
    plan["mode"] = mode
    return plan


def resolve_render(job: dict) -> dict:
    """Combina: padrão do presets.json < opções do job < ajustes do plano (render)."""
    d = presets().get("defaults", {})
    opts = job["options"] or {}
    r = (job["plan"] or {}).get("render") or {}
    out = {
        "layout": opts.get("layout") or d.get("layout") or settings().cut_layout,
        "subtitle_preset": opts.get("subtitle_preset") or d.get("subtitle_preset"),
        **{k: opts[k] for k in ("crop_x", "top_box", "bottom_box") if k in opts},
    }
    if r.get("layout"):
        out["layout"] = r["layout"]
    if r.get("subtitle_preset"):
        out["subtitle_preset"] = r["subtitle_preset"]
    if r.get("crop_x", -1) is not None and r.get("crop_x", -1) >= 0:
        out["crop_x"] = r["crop_x"]
    return out


def preview(job: dict) -> str:
    """Prévia legível do roteiro do corte (para aprovação)."""
    p = job["plan"]
    if not p:
        return "ainda sem plano"
    out = [
        f"CORTE #{job['id']} (v{job['plan_version']}) — {p['title']}",
        f"Fonte: {job['source_title']} ({job['source_channel']})",
        f"Duração: {p['duration_s']:.0f}s em {len(p['segments'])} segmento(s)",
        f"Texto na tela: {p['hook_text']}",
    ]
    if p.get("changes"):
        out.append(f"Alterações: {p['changes']}")
    out.append("")
    for i, sg in enumerate(p["segments"], 1):
        out += [f"[{i}] {fmt_ts(sg['start'])} → {fmt_ts(sg['end'])}  ({sg['end'] - sg['start']:.0f}s, {sg['purpose']})",
                f"    \"{sg['text']}\"", ""]
    out += [f"Por que funciona: {p['why']}", "",
            f"Legenda do post: {p['caption']}", "Hashtags: " + " ".join("#" + h.lstrip('#') for h in p["hashtags"])]
    if p.get("alternatives"):
        out += ["", "Alternativas:"]
        out += [f"  - {fmt_ts(a['start'])} → {fmt_ts(a['end'])}: {a['summary']}" for a in p["alternatives"]]
    return "\n".join(out)
