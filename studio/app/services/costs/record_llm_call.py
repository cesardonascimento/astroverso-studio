from decimal import Decimal

from sqlalchemy.orm import Session

from app.ai.claude import ClaudeUsage
from app.models import Generation, LlmCall


class RecordLlmCall:
    def __init__(self, session: Session):
        self.session = session

    def execute(self, generation: Generation | None, step: str, usage: ClaudeUsage) -> LlmCall:
        call = LlmCall(generation_id=generation.id if generation else None, step=step, model=usage.model,
                       input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
                       cost_usd=Decimal(str(usage.cost_usd)), duration_ms=usage.duration_ms, ok=usage.error is None,
                       error=usage.error)
        self.session.add(call)
        if generation is not None:
            generation.cost_usd = (generation.cost_usd or Decimal(0)) + call.cost_usd
        return call
