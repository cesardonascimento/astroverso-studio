import json
import re
from dataclasses import dataclass

from app.config import CONTENT_DIR, settings
from app.lib.content import ReadMarkdown
from app.lib.media import Word
from app.models import Generation, VersionKind
from app.services.catalog import AUTO_STRATEGY, ListSubtitlePresets, Network


@dataclass
class CutPrompt:
    system: str
    user: str
    version: str


class BuildCutPrompt:
    def execute(self, generation: Generation, network: Network, strategy: str, words: list[Word], kind: str,
                request: str | None, current_plan: dict | None) -> CutPrompt:
        prompt = ReadMarkdown().execute(CONTENT_DIR / "algorithms" / "corte" /
                                        ("revise.md" if kind == VersionKind.REVISION else "plan.md"))
        system = "\n\n".join([prompt.body, self._network_block(network), self._strategy_block(network, strategy)])
        parts = [self._context_block(generation, network)]
        if kind == VersionKind.REVISION:
            parts.append(f"PLANO ATUAL:\n{json.dumps(self._current_for_revision(current_plan), ensure_ascii=False)}")
            parts.append(f"PEDIDO DE ALTERAÇÃO DO EDITOR:\n{request}")
        else:
            instructions = "\n".join(text for text in (generation.inputs.get("instructions"), request) if text)
            if instructions:
                parts.append(f"INSTRUÇÕES DO EDITOR:\n{instructions}")
            if kind == VersionKind.REPLAN:
                parts.append("É um novo pedido para um corte que o editor não aprovou. Proponha algo diferente, "
                             "seguindo o pedido.")
        parts.append(self._transcript_block(words))
        return CutPrompt(system=system, user="\n\n".join(parts), version=str(prompt.meta.get("version", "0")))

    def _network_block(self, network: Network) -> str:
        return (f"REDE DE DESTINO: {network.name}\n{network.guidance}\n"
                f"Duração do corte: de {network.min_duration_s} a {network.max_duration_s} segundos.\n"
                f"Legenda do post: {network.caption}. Hashtags: {network.hashtags}.\n"
                f"Escreva no idioma {settings().content_language}.")

    def _strategy_block(self, network: Network, strategy: str) -> str:
        chosen = [item for item in network.strategies if strategy == AUTO_STRATEGY or item.name == strategy]
        header = ("ESTRATÉGIAS DISPONÍVEIS: escolha a que mais combina com o vídeo e siga só ela."
                  if strategy == AUTO_STRATEGY else "ESTRATÉGIA:")
        return header + "\n\n" + "\n\n".join(f"### {item.name}\n{item.description}\n\n{item.text}" for item in chosen)

    def _context_block(self, generation: Generation, network: Network) -> str:
        presets = {preset.name: preset.description for preset in ListSubtitlePresets().execute()}
        return (f"Vídeo: {generation.source.get('title')} (canal {generation.source.get('channel')})\n"
                f"Duração máxima do corte: {network.max_duration_s} segundos.\n"
                f"Presets de legenda: {json.dumps(presets, ensure_ascii=False)}\n"
                "Layouts: auto, crop (tela cheia cortando as laterais), fit_blur (vídeo inteiro com fundo "
                "desfocado), split (duas regiões empilhadas).")

    def _current_for_revision(self, plan: dict | None) -> dict:
        plan = plan or {}
        current = {key: plan.get(key) for key in ("strategy", "title", "hook_text", "caption", "hashtags", "render")}
        current["segments"] = [{"start": segment.get("text_start", segment["start"]),
                                "end": segment.get("text_end", segment["end"]),
                                "purpose": segment.get("purpose", ""), "text": segment.get("text", "")}
                               for segment in plan.get("segments", [])]
        return current

    def _transcript_block(self, words: list[Word]) -> str:
        return "TRANSCRIÇÃO ([início em segundos] texto):\n" + "\n".join(
            f"[{line[0].start:.1f}] {' '.join(word.text for word in line)}" for line in self._lines(words))

    def _lines(self, words: list[Word], max_words: int = 14) -> list[list[Word]]:
        lines, current = [], []
        for index, word in enumerate(words):
            current.append(word)
            pause = index + 1 < len(words) and words[index + 1].start - word.end > 0.6
            if len(current) >= max_words or re.search(r"[.!?]$", word.text) or pause:
                lines.append(current)
                current = []
        if current:
            lines.append(current)
        return lines
