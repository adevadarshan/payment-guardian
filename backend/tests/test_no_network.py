# tests/test_no_network.py — Slice 3: analyzers are strictly offline.
# URL/message/QR analysis must never touch the network: no DNS, no fetching.
import socket


from app.analyzers import message_analyzer, url_analyzer


def test_analyzers_import_no_network_modules():
    # sys.modules always contains httpx/socket via the FastAPI TestClient, so
    # assert on analyzer source instead: no network imports may appear there.
    for module in (message_analyzer, url_analyzer):
        source = open(module.__file__, encoding="utf-8").read()
        for banned in ("import socket", "import httpx", "import requests",
                       "urllib.request", "urlopen", "socket.create_connection"):
            assert banned not in source, (module.__name__, banned)


def test_shortener_resolved_without_traffic(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", _boom)
    monkeypatch.setattr(socket, "getaddrinfo", _boom)
    signals, _ = url_analyzer.analyze_url("https://bit.ly/3xYzAbC")
    assert any(s.name == "url.shortener" for s in signals)
