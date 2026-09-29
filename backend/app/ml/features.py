# app/ml/features.py — versioned feature schema FEATURES_V1 (Slice 4).
# Features are assembled ONLY from already-computed analyzer inputs for
# payment analyses. Fixed order, fixed length. Any change requires a new
# schema version; the loader rejects mismatches loudly.
import math

from app.pipeline import rules

SCHEMA_VERSION = "FEATURES_V1"
N_FEATURES = 9
MAX_LOG_AMOUNT = math.log1p(200000.0)


def build(payment, *, hour: int | None) -> list[float]:
    """Build the FEATURES_V1 vector. All values roughly in [0, 1]."""
    tier_points, _ = rules.amount_tier(payment.amount)
    cat_points, _ = rules.category_points(payment.merchant_category)
    h_points, band = rules.hour_points(hour)
    family, _ = rules.note_hits(payment.note)
    return [
        math.log1p(payment.amount) / MAX_LOG_AMOUNT,
        min(1.0, rules.drain_ratio(payment.amount, payment.sender_balance)),
        tier_points / 50.0,
        cat_points / 25.0,
        1.0 if band == "night" else 0.0,
        1.0 if band == "late" else 0.0,
        1.0 if family == "urgent" else 0.0,
        1.0 if family == "info" else 0.0,
        1.0 if rules.payee_unverified(payment.payee_name) else 0.0,
    ]
