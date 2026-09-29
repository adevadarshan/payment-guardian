# app/pipeline/signals.py — the single Signal type + fusion weight table (Slice 3).
from dataclasses import dataclass
from typing import Literal


# One weight table for all fusion. Slice 3: everything 1.0 (present so that
# retuning has exactly one place; weights apply only inside fuse.py).
WEIGHTS: dict[str, float] = {}


@dataclass(frozen=True)
class Signal:
    name: str
    source: Literal["rule"] = "rule"
    value: float | None = None
    contribution: float = 0
    observation: str = ""
    title: str = ""
    impact: str = "low"
    # Tie-break rank for reason ordering (lower first). Payment ceilings use 0;
    # cross-type signals default to 9 (alphabetical within equal contribution).
    rank: int = 9

    def weight(self) -> float:
        return WEIGHTS.get(self.name, 1.0)

    def to_reason(self) -> dict:
        return {
            "code": self.name,
            "signal": self.name,
            "title": self.title or self.name,
            "observation": self.observation,
            "impact": self.impact,
        }

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "source": self.source,
            "value": self.value,
            "weight": None,
            "contribution": self.contribution,
        }


def known_signal(name: str) -> bool:
    """Registry check: every emitted signal name must be constructed here."""
    return isinstance(name, str) and len(name) > 0 and "." in name
