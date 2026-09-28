# Weighted risk scorer for Slice 3 — deterministic, explainable, NOT a calibrated probability
# Scores are heuristic severity indicators: higher means a more severe matched-signal pattern.

SIGNAL_WEIGHTS = {
    "urgency": 0.10,
    "reward_or_prize": 0.15,
    "refund_claim": 0.15,
    "payment_request": 0.25,
    "otp_or_pin_request": 0.30,
    "account_or_credential_request": 0.25,
    "scan_or_click_action": 0.15,
    "impersonation": 0.10,
}

COMBINATION_BONUSES = [
    ({"otp_or_pin_request", "payment_request"}, 0.15),
    ({"impersonation", "account_or_credential_request"}, 0.10),
    ({"reward_or_prize", "payment_request"}, 0.10),
    ({"urgency", "otp_or_pin_request"}, 0.10),
]

RECOMMENDED_ACTIONS = {
    "LOW": "No significant risk signals detected. Stay alert and verify independently.",
    "MEDIUM": "Some suspicious signals detected. Verify through official channels before acting.",
    "HIGH": "Multiple scam indicators detected. Do not proceed without independent verification.",
    "CRITICAL": "Strong scam pattern detected. Do not proceed. Do not share OTPs, PINs, or personal information.",
}


def level_for_score(score: float) -> str:
    if score < 0.20:
        return "LOW"
    if score < 0.50:
        return "MEDIUM"
    if score < 0.80:
        return "HIGH"
    return "CRITICAL"


def score(signals: list[dict]) -> dict:
    matched_map = {s["type"]: s for s in signals if s["matched"]}
    raw = sum(SIGNAL_WEIGHTS[t] for t in matched_map if t in SIGNAL_WEIGHTS)
    explanation = [
        f"{s['type']} (+{SIGNAL_WEIGHTS[s['type']]:.2f}): {', '.join(s['evidence'])}"
        for s in signals
        if s["matched"] and s["type"] in SIGNAL_WEIGHTS
    ]
    for members, bonus in COMBINATION_BONUSES:
        if all(m in matched_map for m in members):
            raw += bonus
            explanation.append(f"combination bonus (+{bonus:.2f}): {' + '.join(sorted(members))}")
    risk_score = round(min(max(raw, 0.0), 1.0), 2)
    risk_level = level_for_score(risk_score)
    return {
        "risk_level": risk_level,
        "risk_score": risk_score,
        "signals": explanation,
        "recommended_action": RECOMMENDED_ACTIONS[risk_level],
        "analyzed_by": "weighted_scorer_v1",
    }
