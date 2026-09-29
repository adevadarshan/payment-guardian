# app/pipeline/thresholds.py — the single threshold source (Slice 2).
# MEDIUM begins at 35, HIGH begins at 75. Boundaries are lower-edge inclusive.

from typing import Literal

from app.config import settings

RiskLevel = Literal["SAFE", "MEDIUM", "HIGH"]


def classify(score: int) -> RiskLevel:
    if score >= settings.THRESHOLD_HIGH:
        return "HIGH"
    if score >= settings.THRESHOLD_MEDIUM:
        return "MEDIUM"
    return "SAFE"
