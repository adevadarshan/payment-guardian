# tests/test_normalization.py — Slice 3 increment 1.
from app.pipeline import normalize as nz


def test_text_cap_and_flag():
    out, truncated = nz.normalize_text("  Hello   WORLD  ")
    assert (out, truncated) == ("hello world", False)
    out, truncated = nz.normalize_text("x" * 5000, cap=100)
    assert out == "x" * 100 and truncated is True


def test_leet_and_homoglyph_folding():
    out, _ = nz.normalize_text("V3rify 0TP n0w")
    assert out == "verify otp now"
    out, _ = nz.normalize_text("раураl")  # Cyrillic look-alikes
    assert out == "paypal"


def test_numbers_survive_folding():
    out, _ = nz.normalize_text("Pay Rs.5000 in 10 minutes, OTP 482913")
    assert "5000" in out and "10 minutes" in out and "482913" in out
    out, _ = nz.normalize_text("bl0cked p4ssword")
    assert out == "blocked password"


def test_extract_urls_capped_deduped():
    text = "see https://a.example/x and https://a.example/x plus www.b.example/y ok"
    urls = nz.extract_urls(text)
    assert urls == ["https://a.example/x", "www.b.example/y"]


def test_normalize_url_parts_and_errors():
    parts = nz.normalize_url("HTTPS://Example.COM:443/a?b=c")
    assert parts["scheme"] == "https" and parts["host"] == "example.com"
    assert parts["port"] is None
    for bad in ("", "://", "http:///"):
        try:
            nz.normalize_url(bad)
        except ValueError:
            continue
        raise AssertionError(bad)


def test_qr_hash_stable_across_variants():
    a = nz.normalize_qr_payload("upi://pay?pa=x@y&pn=Shop&am=10")
    b = nz.normalize_qr_payload("  UPI://pay?am=10&pn=Shop&pa=x@y  ")
    assert nz.qr_payload_hash(a) == nz.qr_payload_hash(b)
    assert len(nz.qr_payload_hash(a)) == 64
