import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from backend.main import app
from backend import mock_analyzer

client = TestClient(app)


def test_analyze_high_risk_message():
    response = client.post(
        "/api/analyze",
        json={"message": "Congratulations! You have received a refund. Scan the QR code immediately to claim it."},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] == "HIGH"
    assert data["risk_score"] == 0.55
    assert data["analyzed_by"] == "explainer_v1"
    assert data["summary"] != ""
    assert len(data["explanation"]) > 0
    scorer_text = " ".join(data["signals"])
    for entry in data["explanation"]:
        quoted = re.findall(r'"([^"]+)"', entry)
        assert len(quoted) >= 1
        for term in quoted:
            assert term in scorer_text


def test_analyze_low_risk_message():
    response = client.post(
        "/api/analyze",
        json={"message": "Hello, your monthly statement is ready."},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] == "LOW"
    assert data["risk_score"] == 0.00
    assert data["explanation"] == []
    assert data["actions"] == ["No action needed. Stay alert and verify independently."]
    assert data["summary"] != ""


def test_analyze_empty_message_returns_400():
    response = client.post("/api/analyze", json={"message": ""})
    assert response.status_code == 400


def test_analyze_missing_message_field_returns_422():
    response = client.post("/api/analyze", json={})
    assert response.status_code == 422


def test_mock_analyzer_unit():
    first = mock_analyzer.analyze("Congratulations! Scan the QR to claim your refund now.")
    second = mock_analyzer.analyze("Congratulations! Scan the QR to claim your refund now.")
    assert first == second
    assert first["risk_level"] == "MEDIUM"
    assert first["risk_score"] == 0.45
    assert first["analyzed_by"] == "explainer_v1"


def test_real_signals_in_response():
    response = client.post(
        "/api/analyze",
        json={"message": "Congratulations! You have received a refund. Scan the QR code immediately to claim it."},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["signals"], list)
    assert len(data["signals"]) > 0
    assert any("reward_or_prize" in s or "refund_claim" in s for s in data["signals"])


def test_critical_risk_message():
    response = client.post(
        "/api/analyze",
        json={"message": "RBI alert: Your KYC is pending. Share Aadhaar and OTP immediately or your account will be blocked. Send ₹100 processing fee via UPI."},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] == "CRITICAL"
    assert data["risk_score"] == 1.00
    assert "Do not share OTPs, PINs, or codes with anyone, even if the message asks." in data["actions"]
