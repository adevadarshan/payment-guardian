# app/pipeline/fuse.py — deterministic weighted-sum fusion (Slice 3).
# Single function. No branches per analysis type. Pure.
from app.pipeline.signals import Signal


def fuse(signals: list[Signal], *, weights: dict[str, float] | None = None) -> int:
    """Weighted sum of contributions, clamped to 0-100."""
    table = weights if weights is not None else {}
    total = sum(sig.contribution * table.get(sig.name, 1.0) for sig in signals)
    return max(0, min(100, round(total)))
