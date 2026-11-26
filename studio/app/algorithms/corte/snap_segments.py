from app.lib.media import Word

PAD_START, PAD_END = 0.10, 0.25


class SnapSegments:
    def execute(self, segments: list[dict], words: list[Word], source_duration: float) -> list[dict]:
        snapped = []
        for segment in segments:
            inside = [word for word in words
                      if word.start >= segment["start"] - 0.05 and word.start < segment["end"] - 0.05]
            if not inside:
                continue
            snapped.append({"start": round(max(0.0, inside[0].start - PAD_START), 3),
                            "end": round(min(source_duration, inside[-1].end + PAD_END), 3),
                            "purpose": segment.get("purpose", ""), "text_start": inside[0].start,
                            "text_end": inside[-1].end, "text": " ".join(word.text for word in inside)})
        for current, following in zip(snapped, snapped[1:]):
            if current["start"] < following["start"] < current["end"]:
                current["end"] = following["start"]
        return snapped


class KeepUnchangedSegments:
    def execute(self, segments: list[dict], previous: list[dict], words: list[Word],
                source_duration: float) -> list[dict]:
        result = []
        for segment in segments:
            same = next((old for old in previous
                         if abs(segment["start"] - old.get("text_start", old["start"])) < 0.4
                         and abs(segment["end"] - old.get("text_end", old["end"])) < 0.4), None)
            if same:
                result.append({**same, "purpose": segment.get("purpose") or same.get("purpose", "")})
            else:
                result.extend(SnapSegments().execute([segment], words, source_duration))
        return result
