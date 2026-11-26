from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Word":
        return cls(text=data["text"], start=float(data["start"]), end=float(data["end"]))


@dataclass(frozen=True)
class Segment:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start
