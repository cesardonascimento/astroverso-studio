"""Camada de LLM. Hoje: Claude. Interface pequena para poder trocar de fornecedor.

Toda saída é JSON validado por um modelo Pydantic (structured outputs).
"""
from __future__ import annotations

import copy
import json
import logging
import time
from typing import Any, TypeVar

import anthropic
from pydantic import BaseModel

from .config import LLM_PRICES, WEB_SEARCH_PRICE_PER_REQUEST, settings
from .db import record_generation

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class LLMRefusal(RuntimeError):
    pass


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """JSON schema do Pydantic no formato exigido pelo structured outputs:
    todo objeto com additionalProperties=false e todos os campos obrigatórios."""
    schema = copy.deepcopy(model.model_json_schema())

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            # remove só as palavras-chave de schema, nunca nomes de campo dentro de "properties"
            node.pop("title", None)
            node.pop("default", None)
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"].keys())
                for prop in node["properties"].values():
                    walk(prop)
            for k, v in node.items():
                if k != "properties":
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(schema)
    return schema


class Claude:
    provider = "anthropic"

    def __init__(self) -> None:
        s = settings()
        if not s.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY não configurada no .env")
        self.client = anthropic.Anthropic(api_key=s.anthropic_api_key, max_retries=4)

    def structured(
        self,
        *,
        step: str,
        system: str,
        user: str,
        output: type[T],
        model: str | None = None,
        web_search: int = 0,
        max_tokens: int = 32000,
        ctx: dict[str, Any] | None = None,
    ) -> T:
        """Uma chamada → objeto validado. web_search>0 liga a busca na web (máx. N buscas)."""
        model = model or settings().llm_model
        ctx = ctx or {}
        kwargs: dict[str, Any] = dict(
            model=model,
            max_tokens=max_tokens,
            system=system,
            output_config={"format": {"type": "json_schema", "schema": strict_schema(output)}},
            # fallback automático do servidor caso o modelo recuse por falso positivo de segurança
            extra_headers={"anthropic-beta": "server-side-fallback-2026-07-01"},
            extra_body={"fallbacks": "default"},
        )
        if web_search:
            kwargs["tools"] = [{"type": "web_search_20260209", "name": "web_search", "max_uses": web_search}]

        messages: list[dict[str, Any]] = [{"role": "user", "content": user}]
        t0 = time.monotonic()
        in_tok = out_tok = searches = 0
        try:
            # streaming evita timeout HTTP em respostas longas
            for _ in range(5):  # pause_turn: turno longo com ferramenta de servidor
                with self.client.messages.stream(messages=messages, **kwargs) as stream:
                    resp = stream.get_final_message()
                in_tok += resp.usage.input_tokens
                out_tok += resp.usage.output_tokens
                stu = getattr(resp.usage, "server_tool_use", None)
                searches += getattr(stu, "web_search_requests", 0) or 0
                if resp.stop_reason != "pause_turn":
                    break
                messages = messages + [{"role": "assistant", "content": resp.content}]

            if resp.stop_reason == "refusal":
                raise LLMRefusal(f"modelo recusou: {getattr(resp, 'stop_details', None)}")
            if resp.stop_reason == "max_tokens":
                raise RuntimeError("resposta cortada por max_tokens")
            text = next(b.text for b in reversed(resp.content) if b.type == "text")
            result = output.model_validate(json.loads(text))
        except Exception as e:
            self._record(step, model, in_tok, out_tok, searches, t0, ctx, ok=False, error=repr(e)[:2000])
            raise
        self._record(step, model, in_tok, out_tok, searches, t0, ctx, ok=True)
        return result

    def _record(self, step, model, in_tok, out_tok, searches, t0, ctx, ok, error=None):
        pin, pout = LLM_PRICES.get(model, (0.0, 0.0))
        cost = in_tok / 1e6 * pin + out_tok / 1e6 * pout + searches * WEB_SEARCH_PRICE_PER_REQUEST
        record_generation(
            step=step,
            provider=self.provider,
            model=model,
            input_tokens=in_tok,
            output_tokens=out_tok,
            units=searches,
            cost_usd=round(cost, 5),
            duration_ms=int((time.monotonic() - t0) * 1000),
            ok=ok,
            error=error,
            **{k: ctx[k] for k in ("video_id", "idea_id", "snapshot_id") if k in ctx},
        )


class ClaudeCode:
    """Claude via CLI do Claude Code em modo headless (`claude -p`), usando a ASSINATURA
    (token de `claude setup-token` em CLAUDE_CODE_OAUTH_TOKEN). Sem custo por chamada, mas
    consome os limites do plano. Para produção, use LLM_PROVIDER=anthropic (API)."""

    provider = "claude_code"

    def __init__(self) -> None:
        import os
        import shutil

        if not shutil.which("claude"):
            raise RuntimeError("CLI 'claude' não encontrado na imagem")
        if not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
            raise RuntimeError("CLAUDE_CODE_OAUTH_TOKEN não configurado no .env (gere com `claude setup-token`)")

    def structured(self, *, step: str, system: str, user: str, output: type[T], model: str | None = None,
                   web_search: int = 0, max_tokens: int = 32000, ctx: dict[str, Any] | None = None) -> T:
        import subprocess
        import tempfile

        model = model or settings().llm_model
        ctx = ctx or {}
        t0 = time.monotonic()
        data: dict[str, Any] = {}
        with tempfile.TemporaryDirectory() as tmp:  # cwd vazio: não carrega CLAUDE.md nem configs de projeto
            sp = f"{tmp}/system.md"
            with open(sp, "w", encoding="utf-8") as f:
                f.write(system)
            tools = "WebSearch" if web_search else ""
            args = [
                "claude", "-p",
                "--system-prompt-file", sp,
                "--json-schema", json.dumps(strict_schema(output)),
                "--output-format", "json",
                "--model", model,
                "--tools", tools,
                "--setting-sources", "",
                "--strict-mcp-config",
                "--no-session-persistence",
            ]
            if web_search:
                args += ["--allowedTools", "WebSearch"]
            try:
                p = subprocess.run(args, input=user, capture_output=True, text=True, cwd=tmp, timeout=900)
                try:
                    data = json.loads(p.stdout)
                except json.JSONDecodeError:
                    raise RuntimeError(f"claude CLI saiu com {p.returncode}: {(p.stderr or p.stdout)[-2000:]}")
                if data.get("is_error") or data.get("subtype") != "success":
                    raise RuntimeError(f"claude CLI erro ({data.get('subtype')}, "
                                       f"status={data.get('api_error_status')}): {str(data.get('result'))[:1500]}")
                if data.get("structured_output") is None:
                    raise RuntimeError(
                        f"claude CLI não devolveu structured_output (stop={data.get('stop_reason')}, "
                        f"terminal={data.get('terminal_reason')}, turns={data.get('num_turns')}, "
                        f"denials={data.get('permission_denials')}): {str(data.get('result'))[:800]}")
                result = output.model_validate(data["structured_output"])
            except Exception as e:
                self._record(step, model, data, t0, ctx, ok=False, error=repr(e)[:2000])
                raise
        self._record(step, model, data, t0, ctx, ok=True)
        return result

    def _record(self, step, model, data, t0, ctx, ok, error=None):
        u = data.get("usage") or {}
        stu = u.get("server_tool_use") or {}
        record_generation(
            step=step, provider=self.provider, model=model,
            input_tokens=(u.get("input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0)
            + (u.get("cache_read_input_tokens") or 0),
            output_tokens=u.get("output_tokens"),
            units=stu.get("web_search_requests") or 0,
            cost_usd=0,  # coberto pela assinatura
            meta={"api_equivalent_usd": data.get("total_cost_usd"), "num_turns": data.get("num_turns")},
            duration_ms=int((time.monotonic() - t0) * 1000), ok=ok, error=error,
            **{k: ctx[k] for k in ("video_id", "idea_id", "snapshot_id") if k in ctx},
        )


_llm: Claude | ClaudeCode | None = None


def llm() -> Claude | ClaudeCode:
    global _llm
    if _llm is None:
        _llm = {"anthropic": Claude, "claude_code": ClaudeCode}[settings().llm_provider]()
    return _llm


def load_prompt(name: str) -> tuple[str, str]:
    """Lê prompts/<name>.md. A primeira linha `version: X` vira a versão do prompt."""
    text = (settings().prompts_dir / f"{name}.md").read_text(encoding="utf-8")
    first, _, rest = text.partition("\n")
    if first.lower().startswith("version:"):
        return first.split(":", 1)[1].strip(), rest.strip()
    return "0", text.strip()
