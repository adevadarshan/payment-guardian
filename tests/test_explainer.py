import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import explainer, signal_extractor, risk_scorer

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

LOW_SUMMARY = "Low risk: no significant warning signals were found in this message. Stay alert and verify independently."
MEDIUM_SUMMARY = "Medium risk: this message contains some suspicious signals. Verify through official channels before acting."
HIGH_SUMMARY = "High risk: this message contains several warning signals. Do not proceed without independent verification."
CRITICAL_SUMMARY = "Critical risk: this message shows a strong pattern of warning signals. Do not proceed."
DEFAULT_ACTION = "No action needed. Stay alert and verify independently."

BANNED = ["definitely a scam", "confirmed fraud", "100% safe", "guaranteed", "probability", "likelihood", "chance of fraud"]


def _make_assessment(*matched_types, level="MEDIUM", score=0.25):
    signals = [
        {
            "type": t,
            "matched": t in matched_types,
            "evidence": ["evidence-%s" % t] if t in matched_types else [],
        }
        for t in SIGNAL_ORDER
    ]
    return signals, level, score


def test_low_summary_no_signals():
    signals, level, score = _make_assessment(level="LOW", score=0.00)
    result = explainer.build_explanation(signals, level, score)
    assert result["summary"] == LOW_SUMMARY
    assert result["explanation"] == []
    assert result["actions"] == [DEFAULT_ACTION]


def test_medium_summary():
    signals, level, score = _make_assessment("urgency", "reward_or_prize", level="MEDIUM", score=0.25)
    result = explainer.build_explanation(signals, level, score)
    assert result["summary"] == MEDIUM_SUMMARY


def test_high_summary():
    signals, level, score = _make_assessment(
        "urgency", "reward_or_prize", "refund_claim", "scan_or_click_action", level="HIGH", score=0.55
    )
    result = explainer.build_explanation(signals, level, score)
    assert result["summary"] == HIGH_SUMMARY


def test_critical_summary():
    signals, level, score = _make_assessment(
        "urgency", "payment_request", "otp_or_pin_request",
        "account_or_credential_request", "impersonation",
        level="CRITICAL", score=1.00,
    )
    result = explainer.build_explanation(signals, level, score)
    assert result["summary"] == CRITICAL_SUMMARY


def test_single_signal_explanation():
    signals, level, score = _make_assessment("otp_or_pin_request")
    result = explainer.build_explanation(signals, level, score)
    assert len(result["explanation"]) == 1
    assert '"evidence-otp_or_pin_request"' in result["explanation"][0]
    assert result["explanation"][0].startswith("The message involves a one-time password")


def test_each_signal_has_rule():
    for signal_type in SIGNAL_ORDER:
        signals, level, score = _make_assessment(signal_type)
        result = explainer.build_explanation(signals, level, score)
        assert len(result["explanation"]) == 1, signal_type
        assert '"evidence-%s"' % signal_type in result["explanation"][0], signal_type


def test_multiple_signals_order():
    signals, level, score = _make_assessment(
        "reward_or_prize", "refund_claim", "scan_or_click_action", "urgency",
        level="HIGH", score=0.55,
    )
    result = explainer.build_explanation(signals, level, score)
    assert len(result["explanation"]) == 4
    # extractor input order: urgency, reward, refund, ..., scan
    assert "evidence-urgency" in result["explanation"][0]
    assert "evidence-reward_or_prize" in result["explanation"][1]
    assert "evidence-refund_claim" in result["explanation"][2]
    assert "evidence-scan_or_click_action" in result["explanation"][3]


def test_actions_match_signals():
    signals, level, score = _make_assessment("otp_or_pin_request", "payment_request")
    result = explainer.build_explanation(signals, level, score)
    assert result["actions"] == [
        explainer.ACTIONS["payment_request"],
        explainer.ACTIONS["otp_or_pin_request"],
    ]


def test_actions_deduplicated():
    original = dict(explainer.ACTIONS)
    try:
        explainer.ACTIONS["urgency"] = "Same action."
        explainer.ACTIONS["reward_or_prize"] = "Same action."
        signals, level, score = _make_assessment("urgency", "reward_or_prize")
        result = explainer.build_explanation(signals, level, score)
        assert result["actions"] == ["Same action."]
    finally:
        explainer.ACTIONS.clear()
        explainer.ACTIONS.update(original)


def test_no_invented_evidence():
    signals, level, score = _make_assessment("urgency")
    result = explainer.build_explanation(signals, level, score)
    blob = " ".join(result["explanation"] + result["actions"])
    for other in [t for t in SIGNAL_ORDER if t != "urgency"]:
        assert other not in blob
    assert "lottery" not in blob


def test_traceability_invariant():
    message = "Congratulations! Scan the QR to claim your refund immediately."
    signals = signal_extractor.analyze(message)
    scored = risk_scorer.score(signals)
    result = explainer.build_explanation(signals, scored["risk_level"], scored["risk_score"])
    evidence_by_type = {s["type"]: s["evidence"] for s in signals}
    matched = {s["type"] for s in signals if s["matched"]}
    assert len(result["explanation"]) == len(matched)
    assert len(result["explanation"]) > 0
    for entry in result["explanation"]:
        quoted = re.findall(r'"([^"]+)"', entry)
        assert len(quoted) >= 1  # template slot must survive
        owners = [t for t in matched if any(q in evidence_by_type[t] for q in quoted)]
        assert owners, entry
        for q in quoted:
            assert any(q in evidence_by_type[t] for t in matched), q


def test_unknown_signal_ignored():
    signals, level, score = _make_assessment("urgency")
    signals.append({"type": "future_signal_x", "matched": True, "evidence": ["mystery"]})
    result = explainer.build_explanation(signals, level, score)
    assert len(result["explanation"]) == 1
    assert "future_signal_x" not in " ".join(result["explanation"])
    assert "mystery" not in " ".join(result["explanation"] + result["actions"])


def test_unknown_level_fallback():
    signals, level, score = _make_assessment("urgency", level="WEIRD", score=0.99)
    result = explainer.build_explanation(signals, level, score)
    assert result["summary"] == MEDIUM_SUMMARY


def test_empty_signals_list():
    result = explainer.build_explanation([], "LOW", 0.00)
    assert result["summary"] == LOW_SUMMARY
    assert result["explanation"] == []
    assert result["actions"] == [DEFAULT_ACTION]


def test_determinism():
    signals, level, score = _make_assessment(
        "urgency", "payment_request", "otp_or_pin_request", level="HIGH", score=0.65
    )
    first = explainer.build_explanation(signals, level, score)
    second = explainer.build_explanation(signals, level, score)
    assert first == second


def test_no_certainty_language():
    for level in ["LOW", "MEDIUM", "HIGH", "CRITICAL", "WEIRD"]:
        signals, _, _ = _make_assessment(*SIGNAL_ORDER, level=level, score=1.00)
        result = explainer.build_explanation(signals, level, 1.00)
        blob = " ".join([result["summary"]] + result["explanation"] + result["actions"]).lower()
        for phrase in BANNED:
            assert phrase not in blob, (level, phrase)
    source = Path(__file__).resolve().parent.parent.joinpath("backend", "explainer.py").read_text().lower()
    for phrase in BANNED:
        assert phrase not in source, phrase
