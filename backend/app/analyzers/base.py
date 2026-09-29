# app/analyzers/base.py — the Analyzer protocol (Slice 3). ~20 lines by design.
from typing import Protocol

from app.pipeline.signals import Signal


class Analyzer(Protocol):
    name: str

    def matches(self, analysis_type: str) -> bool: ...
    def analyze(self, normalized: object, ctx: dict) -> list[Signal]: ...
