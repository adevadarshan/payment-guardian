import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import risk_scorer

SIGNAL_ORDER = [
    "urgency",
    "reward_or_prize",
    "refund_claim",
    "payment_request",
    "otp_or_pin_request",
    "account_or_credential_request",
    "impersonation",
    "scan_or_click_action",
]


def _make_signals(*matched_types):
    return [
        {
            "type": t,
            "matched": t in matched_types,
            "evidence": [f"evidence-{t}"] if t in matched_types else [],
        }
        for t in SIGNAL_ORDER
    ]


def test_no_signals_score():
    result = risk_scorer.score(_make_signals())
    assert result["risk_score"] == 0.00
    assert result["risk_level"] == "LOW"
    empty = risk_scorer.score([])
    assert empty["risk_score"] == 0.00
    assert empty["risk_level"] == "LOW"


def test_single_urgency():
    result = risk_scorer.score(_make_signals("urgency"))
    assert result["risk_score"] == 0.10
    assert result["risk_level"] == "LOW"


def test_single_otp_request():
    result = risk_scorer.score(_make_signals("otp_or_pin_request"))
    assert result["risk_score"] == 0.30
    assert result["risk_level"] == "MEDIUM"


def test_single_payment_request():
    result = risk_scorer.score(_make_signals("payment_request"))
    assert result["risk_score"] == 0.25
    assert result["risk_level"] == "MEDIUM"


def test_urgency_plus_reward():
    result = risk_scorer.score(_make_signals("urgency", "reward_or_prize"))
    assert result["risk_score"] == 0.25
    assert result["risk_level"] == "MEDIUM"


def test_otp_plus_payment_combo():
    result = risk_scorer.score(_make_signals("otp_or_pin_request", "payment_request"))
    assert result["risk_score"] == 0.70
    assert result["risk_level"] == "HIGH"


def test_impersonation_plus_credential_combo():
    result = risk_scorer.score(_make_signals("impersonation", "account_or_credential_request"))
    assert result["risk_score"] == 0.45
    assert result["risk_level"] == "MEDIUM"


def test_reward_plus_payment_combo():
    result = risk_scorer.score(_make_signals("reward_or_prize", "payment_request"))
    assert result["risk_score"] == 0.50
    assert result["risk_level"] == "HIGH"


def test_urgency_plus_otp_combo():
    result = risk_scorer.score(_make_signals("urgency", "otp_or_pin_request"))
    assert result["risk_score"] == 0.50
    assert result["risk_level"] == "HIGH"


def test_critical_level():
    result = risk_scorer.score(
        _make_signals(
            "otp_or_pin_request",
            "payment_request",
            "urgency",
            "impersonation",
            "account_or_credential_request",
        )
    )
    assert result["risk_score"] == 1.00
    assert result["risk_level"] == "CRITICAL"


def test_score_clamped_at_one():
    result = risk_scorer.score(_make_signals(*SIGNAL_ORDER))
    assert result["risk_score"] == 1.00


def test_score_bounded_zero_to_one():
    for signals in (
        _make_signals(),
        _make_signals("urgency"),
        _make_signals("otp_or_pin_request", "payment_request"),
        _make_signals(*SIGNAL_ORDER),
        [],
    ):
        result = risk_scorer.score(signals)
        assert 0.00 <= result["risk_score"] <= 1.00


def test_risk_level_boundaries():
    assert risk_scorer.level_for_score(0.19) == "LOW"
    assert risk_scorer.level_for_score(0.20) == "MEDIUM"
    assert risk_scorer.level_for_score(0.49) == "MEDIUM"
    assert risk_scorer.level_for_score(0.50) == "HIGH"
    assert risk_scorer.level_for_score(0.79) == "HIGH"
    assert risk_scorer.level_for_score(0.80) == "CRITICAL"


def test_determinism():
    signals = _make_signals("otp_or_pin_request", "payment_request", "urgency")
    assert risk_scorer.score(signals) == risk_scorer.score(signals)


def test_explanation_matches_evidence():
    result = risk_scorer.score(_make_signals("urgency", "reward_or_prize"))
    assert any("urgency" in s for s in result["signals"])
    assert any("reward_or_prize" in s for s in result["signals"])


def test_no_invented_evidence():
    result = risk_scorer.score(_make_signals("urgency"))
    others = [t for t in SIGNAL_ORDER if t != "urgency"]
    assert all(all(t not in s for t in others) for s in result["signals"])


def test_combination_bonus_in_explanation():
    result = risk_scorer.score(_make_signals("otp_or_pin_request", "payment_request"))
    assert any("combination bonus" in s for s in result["signals"])
