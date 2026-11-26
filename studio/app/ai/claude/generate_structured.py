import json
import time
from dataclasses import dataclass
from typing import Generic, TypeVar

import anthropic
from pydantic import BaseModel

from app.ai.claude.prices import cost_usd
from app.ai.claude.strict_schema import BuildStrictSchema

T = TypeVar("T", bound=BaseModel)


class ClaudeRefusal(RuntimeError):
    pass


@dataclass
class ClaudeUsage:
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: int = 0
    error: str | None = None

    @property
    def cost_usd(self) -> float:
        return cost_usd(self.model, self.input_tokens, self.output_tokens)


@dataclass
class StructuredResult(Generic[T]):
    value: T
    usage: ClaudeUsage


PERMANENT_ERRORS = (anthropic.AuthenticationError, anthropic.PermissionDeniedError, anthropic.BadRequestError,
                    anthropic.NotFoundError, ClaudeRefusal)


class ClaudeCallFailed(RuntimeError):
    def __init__(self, message: str, usage: ClaudeUsage, permanent: bool = False):
        super().__init__(message)
        self.usage = usage
        self.permanent = permanent


class GenerateStructured(Generic[T]):
    def __init__(self, api_key: str, model: str, effort: str = "high", max_tokens: int = 32000):
        self.client = anthropic.Anthropic(api_key=api_key, max_retries=4)
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens

    def execute(self, system: str, user: str, output: type[T]) -> StructuredResult[T]:
        usage = ClaudeUsage(model=self.model)
        started = time.monotonic()
        try:
            with self.client.messages.stream(
                model=self.model, max_tokens=self.max_tokens, system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"effort": self.effort,
                               "format": {"type": "json_schema", "schema": BuildStrictSchema().execute(output)}},
                extra_headers={"anthropic-beta": "server-side-fallback-2026-07-01"},
                extra_body={"fallbacks": "default"},
            ) as stream:
                response = stream.get_final_message()
            usage.input_tokens = response.usage.input_tokens
            usage.output_tokens = response.usage.output_tokens
            value = self._parse(response, output)
        except Exception as error:
            usage.duration_ms = int((time.monotonic() - started) * 1000)
            usage.error = repr(error)[:2000]
            raise ClaudeCallFailed(self._describe(error), usage, isinstance(error, PERMANENT_ERRORS)) from error
        usage.duration_ms = int((time.monotonic() - started) * 1000)
        return StructuredResult(value=value, usage=usage)

    def _describe(self, error: Exception) -> str:
        if isinstance(error, anthropic.AuthenticationError):
            return "a chave da API do Claude foi recusada (confira ANTHROPIC_API_KEY no .env)"
        if isinstance(error, anthropic.PermissionDeniedError):
            return "a chave da API do Claude não tem permissão para este modelo"
        return str(error)

    def _parse(self, response, output: type[T]) -> T:
        if response.stop_reason == "refusal":
            raise ClaudeRefusal(f"o modelo recusou: {getattr(response, 'stop_details', None)}")
        if response.stop_reason == "max_tokens":
            raise RuntimeError("resposta cortada por max_tokens")
        text = next(block.text for block in reversed(response.content) if block.type == "text")
        return output.model_validate(json.loads(text))
