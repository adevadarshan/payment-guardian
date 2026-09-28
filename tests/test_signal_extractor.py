import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import signal_extractor


def _by_type(result):
    return {s["type"]: s for s in result}


def test_no_signals_on_clean_message():
    result = signal_extractor.analyze("Hello, your monthly statement is ready.")
    assert len(result) == 8
    assert all(s["matched"] is False for s in result)
    assert all(s["evidence"] == [] for s in result)


def test_urgency_detected():
    sig = _by_type(signal_extractor.analyze("Act now or your account will be suspended immediately."))["urgency"]
    assert sig["matched"] is True
    assert "act now" in sig["evidence"]
    assert "immediately" in sig["evidence"]


def test_reward_or_prize_detected():
    sig = _by_type(signal_extractor.analyze("Congratulations! You have won ₹5,000."))["reward_or_prize"]
    assert sig["matched"] is True
    assert "congratulations" in sig["evidence"]
    assert "you have won" in sig["evidence"]


def test_refund_claim_detected():
    sig = _by_type(signal_extractor.analyze("Your refund has been processed."))["refund_claim"]
    assert sig["matched"] is True
    assert "refund" in sig["evidence"]


def test_payment_request_detected():
    sig = _by_type(signal_extractor.analyze("Please send ₹2,000 via GPay now."))["payment_request"]
    assert sig["matched"] is True
    assert "gpay" in sig["evidence"]


def test_otp_request_detected():
    sig = _by_type(signal_extractor.analyze("Share the OTP sent to your mobile."))["otp_or_pin_request"]
    assert sig["matched"] is True
    assert "otp" in sig["evidence"]


def test_account_credential_detected():
    sig = _by_type(signal_extractor.analyze("Please share your Aadhaar number for KYC."))["account_or_credential_request"]
    assert sig["matched"] is True
    assert "aadhaar" in sig["evidence"]
    assert "kyc" in sig["evidence"]


def test_impersonation_detected():
    sig = _by_type(signal_extractor.analyze("This is an official message from RBI."))["impersonation"]
    assert sig["matched"] is True
    assert "rbi" in sig["evidence"]


def test_scan_click_detected():
    sig = _by_type(signal_extractor.analyze("Scan the QR code to claim your prize."))["scan_or_click_action"]
    assert sig["matched"] is True
    assert "scan the qr" in sig["evidence"] or "qr code" in sig["evidence"]


def test_multiple_signals_in_one_message():
    by_type = _by_type(signal_extractor.analyze("Congratulations! Scan the QR to claim your refund. Share OTP to complete."))
    assert by_type["reward_or_prize"]["matched"] is True
    assert by_type["scan_or_click_action"]["matched"] is True
    assert by_type["refund_claim"]["matched"] is True
    assert by_type["otp_or_pin_request"]["matched"] is True


def test_case_insensitive_matching():
    sig = _by_type(signal_extractor.analyze("CONGRATULATIONS! You Have WON."))["reward_or_prize"]
    assert sig["matched"] is True


def test_legitimate_otp_delivery():
    # Documented false positive: legitimate OTP delivery fires otp_or_pin_request
    sig = _by_type(signal_extractor.analyze("Your OTP is 452310. Do not share it with anyone."))["otp_or_pin_request"]
    assert sig["matched"] is True


def test_all_8_signal_types_always_present():
    result = signal_extractor.analyze("Hello.")
    assert [s["type"] for s in result] == [
        "urgency",
        "reward_or_prize",
        "refund_claim",
        "payment_request",
        "otp_or_pin_request",
        "account_or_credential_request",
        "impersonation",
        "scan_or_click_action",
    ]


def test_determinism():
    msg = "Congratulations! Scan the QR to claim your refund immediately."
    assert signal_extractor.analyze(msg) == signal_extractor.analyze(msg)
