# app/analyzers/ml_analyzer.py — bounded ML signal (Slice 4).
# Payment analyses only. Contribution clamped to ±15. Never selects the level:
# run.py fuses this through the normal path and classifies the final score.
from app.ml.features import build as build_features
from app.ml.registry import ModelHandle
from app.pipeline.signals import Signal

MAX_ABS_CONTRIBUTION = 15


def ml_signal(payment, *, hour: int | None,
              handle: ModelHandle | None) -> Signal | None:
    """Score a payment with the loaded model. None when unavailable."""
    if handle is None:
        return None
    try:
        proba = float(handle.model.predict_proba([build_features(payment, hour=hour)])[0][1])
    except Exception:
        return None
    contribution = max(-MAX_ABS_CONTRIBUTION,
                       min(MAX_ABS_CONTRIBUTION, round((proba - 0.5) * 30)))
    if contribution == 0:
        return None
    impact = "medium" if abs(contribution) >= 10 else "low"
    return Signal(
        name="ml.risk", value=round(proba, 4), contribution=contribution,
        observation=(f"Model {handle.version} estimates "
                     f"{'elevated' if contribution > 0 else 'reduced'} risk "
                     f"(p={proba:.2f})"),
        title="Model assessment", impact=impact, rank=6,
    )
