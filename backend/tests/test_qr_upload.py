# tests/test_qr_upload.py — Slice 3 increment 7: decode, hardening, authority.
# QR fixtures are generated at test time (qrcode[pil], test-only dep);
# no binary blobs are committed. "hello" is valid base64 of plain text.
import base64
import io
import os

import qrcode

from app.analyzers import qr_analyzer
from tests.conftest import client

UPI_PAYLOAD = "upi://pay?pa=shop@upi&pn=Corner Shop&am=250&cu=INR"


def _qr_png_bytes(payload: str) -> bytes:
    img = qrcode.make(payload)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def test_server_decodes_uploaded_qr_image():
    r = client.post("/api/analyze", json={
        "analysis_type": "qr", "qr": {"image_base64": _b64(_qr_png_bytes(UPI_PAYLOAD))}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["evidence"]["decoded"] is True
    assert body["evidence"]["qr_decode"] == "server"
    assert body["evidence"]["payload_class"] == "upi_uri"
    assert body["evidence"]["parsed_qr"]["pa"] == "shop@upi"


def test_decode_authority_image_beats_client_payload():
    r = client.post("/api/analyze", json={
        "analysis_type": "qr",
        "qr": {"image_base64": _b64(_qr_png_bytes(UPI_PAYLOAD)),
               "payload": "https://evil.example/phish"}})
    assert r.status_code == 200
    body = r.json()
    assert body["evidence"]["payload_class"] == "upi_uri"
    assert body["evidence"]["qr_decode"] == "server"


def test_wrong_magic_rejected():
    r = client.post("/api/analyze", json={
        "analysis_type": "qr", "qr": {"image_base64": _b64(b"hello world")}})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "unsupported_media"


def test_corrupt_image_degrades_to_unable():
    r = client.post("/api/analyze", json={
        "analysis_type": "qr",
        "qr": {"image_base64": _b64(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)}})
    assert r.status_code == 200
    body = r.json()
    assert body["seen"]["status"] == "unable_to_verify"
    assert body["evidence"]["decoded"] is False
    assert any(reason["code"] == "qr.unverifiable" for reason in body["reasons"])


def test_oversized_upload_rejected():
    big = os.urandom(6 * 1024 * 1024)
    r = client.post("/api/analyze", json={
        "analysis_type": "qr", "qr": {"image_base64": _b64(big)}})
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "too_large"


def test_pixel_bomb_rejected():
    from PIL import Image
    img = Image.new("RGB", (4000, 4000), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    r = client.post("/api/analyze", json={
        "analysis_type": "qr", "qr": {"image_base64": _b64(buf.getvalue())}})
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "too_large"


def test_decode_helper_unit():
    assert qr_analyzer.sniff_format(_qr_png_bytes(UPI_PAYLOAD)) == "png"
    assert qr_analyzer.sniff_format(b"nope") is None
    try:
        qr_analyzer.decode_image(b"nope", max_bytes=1024, max_megapixels=12)
    except qr_analyzer.DecodeError as exc:
        assert str(exc) == "unsupported_media"
    else:
        raise AssertionError("expected DecodeError")
