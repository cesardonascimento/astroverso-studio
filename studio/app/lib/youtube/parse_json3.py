import re

from app.lib.media import Word

MARKERS = {">>", ">", "-", "–", "—", "&gt;&gt;"}


class ParseJson3:
    def execute(self, data: dict) -> list[Word]:
        drafts: list[list] = []
        for event in data.get("events", []):
            segments = event.get("segs")
            if not segments or "tStartMs" not in event:
                continue
            start = event["tStartMs"] / 1000
            pieces = [(segment.get("utf8", ""), segment.get("tOffsetMs")) for segment in segments]
            if len(pieces) > 1 and any(offset is not None for _, offset in pieces[1:]):
                drafts.extend(self._timed_words(pieces, start))
            else:
                drafts.extend(self._spread_words(pieces, start, event.get("dDurationMs", 0) / 1000))
        return self._close_open_ends(drafts)

    def _timed_words(self, pieces: list[tuple[str, int | None]], start: float) -> list[list]:
        words = []
        for text, offset in pieces:
            text = self._clean(text)
            if not text or text.startswith("["):
                continue
            words.extend([token, round(start + (offset or 0) / 1000, 3), None]
                         for token in text.split() if not self._is_marker(token))
        return words

    def _spread_words(self, pieces: list[tuple[str, int | None]], start: float, duration: float) -> list[list]:
        text = self._clean("".join(piece for piece, _ in pieces))
        if not text or (text.startswith("[") and text.endswith("]")):
            return []
        tokens = [token for token in text.split() if not self._is_marker(token)]
        total = sum(len(token) + 1 for token in tokens)
        words, cursor = [], start
        for token in tokens:
            span = duration * (len(token) + 1) / total if total else 0
            words.append([token, round(cursor, 3), round(cursor + span, 3)])
            cursor += span
        return words

    def _close_open_ends(self, drafts: list[list]) -> list[Word]:
        words = []
        for index, (text, start, end) in enumerate(drafts):
            if end is None:
                following = drafts[index + 1][1] if index + 1 < len(drafts) else start + 0.5
                end = round(min(following, start + 1.0), 3)
            words.append(Word(text, start, end))
        return words

    def _clean(self, text: str) -> str:
        return re.sub(r"\s+", " ", text.replace("\n", " ")).strip()

    def _is_marker(self, token: str) -> bool:
        return token in MARKERS or not any(char.isalnum() for char in token)
