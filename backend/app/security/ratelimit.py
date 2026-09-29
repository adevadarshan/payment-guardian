# app/security/ratelimit.py — in-memory sliding-window rate limiting (Slice 4).
# Single-instance demo/compose scope: process-local state, documented.
# Multi-worker deployments would need a shared store (out of scope).
# Clocks are injectable so tests never sleep.
import time
from typing import Callable

_now: Callable[[], float] = time.time
_windows: dict[str, list[float]] = {}


def set_clock(fn: Callable[[], float]) -> None:
    """Replace the clock (tests only)."""
    global _now
    _now = fn


def reset() -> None:
    """Clear all windows (tests only)."""
    _windows.clear()


def check(key: str, limit: int, window_s: int = 60,
          *, now: float | None = None) -> tuple[bool, float]:
    """Sliding-window check. Returns (allowed, retry_after_seconds)."""
    moment = now if now is not None else _now()
    cutoff = moment - window_s
    hits = [t for t in _windows.get(key, []) if t > cutoff]
    if len(hits) >= limit:
        oldest = min(hits)
        return False, max(0.0, oldest + window_s - moment)
    hits.append(moment)
    _windows[key] = hits
    return True, 0.0
