# tests/test_ml.py — Slice 4 increment 4: registry integrity, bounded signal,
# disabled default. Requires trained artifacts OR skips that need them.
import pytest

from app.ml import registry
from app.schemas.analyze import PaymentInput
from tests.conftest import client, payment_payload


def _valid_artifacts():
    from pathlib import Path
    d = Path(__file__).resolve().parents[1] / "app" / "ml" / "artifacts"
    return d if (d / "model.joblib").exists() and (d / "metadata.json").exists() else None


def test_registry_missing_dir_falls_back_to_none(tmp_path):
    assert registry.load("synthetic-v1", directory=tmp_path / "nope") is None


def test_registry_checksum_mismatch_falls_back(tmp_path):
    import json
    import shutil
    src = _valid_artifacts()
    if src is None:
        pytest.skip("no trained artifacts present")
    shutil.copytree(src, tmp_path / "art")
    meta_path = tmp_path / "art" / "metadata.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["sha256"] = "0" * 64
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    assert registry.load("synthetic-v1", directory=tmp_path / "art") is None


def test_registry_schema_mismatch_falls_back(tmp_path):
    import json
    import shutil
    src = _valid_artifacts()
    if src is None:
        pytest.skip("no trained artifacts present")
    shutil.copytree(src, tmp_path / "art")
    meta_path = tmp_path / "art" / "metadata.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["feature_schema"] = "FEATURES_V999"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    assert registry.load("synthetic-v1", directory=tmp_path / "art") is None


def test_registry_none_backend_never_loads(tmp_path):
    assert registry.load("none", directory=tmp_path) is None


def test_ml_disabled_default_discloses_none():
    body = client.post("/api/analyze", json=payment_payload()).json()
    assert body["model"]["backend"] == "none"
    assert body["model"]["version"] is None
    assert all(not s["name"].startswith("ml.") for s in body["signals"])


def test_ml_signal_bounded_and_versioned():
    src = _valid_artifacts()
    if src is None:
        pytest.skip("no trained artifacts present")
    from app.analyzers import ml_analyzer
    handle = registry.load("synthetic-v1", directory=src)
    assert handle is not None and handle.version == "synthetic-v1"
    payment = PaymentInput(**payment_payload()["payment"])
    sig = ml_analyzer.ml_signal(payment, hour=14, handle=handle)
    if sig is not None:
        assert abs(sig.contribution) <= 15
        assert "synthetic-v1" in sig.observation
    assert ml_analyzer.ml_signal(payment, hour=14, handle=None) is None


def test_ml_on_keeps_golden_bands_documented():
    """With the model enabled, golden scores shift only within the ±15 cap.

    Locked ML-on expectations (measured with synthetic-v1 over the Slice 3
    goldens): 9 of 10 bands hold; exactly one documented flip occurs —
    "info-only note stays safe" moves 34 SAFE -> 36 MEDIUM. That flip is
    accepted as known synthetic-model behavior (the model is default-off and
    disclosed; it approximates our own rules and carries no independent fraud
    knowledge). Any retrain that changes these numbers must update this table
    deliberately.
    """
    import os
    from app.ml import registry as registry_module
    src = _valid_artifacts()
    if src is None:
        pytest.skip("no trained artifacts present")
    os.environ["ML_ARTIFACTS_DIR"] = str(src)
    registry_module.reset()
    import app.config as config_module
    old = config_module.settings.MODEL_BACKEND
    config_module.settings.MODEL_BACKEND = "synthetic-v1"
    EXPECTED = {
        "safe grocery": (1, "SAFE"),
        "suspicious electronics": (40, "MEDIUM"),
        "high-risk demo": (89, "HIGH"),
        "drain 95 percent": (85, "HIGH"),
        "urgent note": (100, "HIGH"),
        "near limit magnitude": (74, "MEDIUM"),
        "info-only note stays safe": (36, "MEDIUM"),
        "night benign": (20, "SAFE"),
        "crypto medium": (52, "MEDIUM"),
        "gambling drain": (85, "HIGH"),
    }
    try:
        from tests.test_golden_payment import CASES
        for case in CASES:
            body = dict(case["payload"])
            body["timestamp"] = case["timestamp"]
            data = client.post("/api/analyze", json=body).json()
            assert (data["risk_score"], data["risk_level"]) == EXPECTED[case["name"]], case["name"]
            assert data["model"]["backend"] == "synthetic-v1"
            assert data["model"]["version"] == "synthetic-v1"
        # Band discipline: at most one level of movement vs Slice 3 bands.
        for case in CASES:
            order = ["SAFE", "MEDIUM", "HIGH"]
            new_level = EXPECTED[case["name"]][1]
            assert abs(order.index(new_level) - order.index(case["level"])) <= 1, case["name"]
    finally:
        config_module.settings.MODEL_BACKEND = old
        del os.environ["ML_ARTIFACTS_DIR"]
        registry_module.reset()

