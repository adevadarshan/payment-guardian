# tests/conftest.py — SQLite-backed app for the suite (Slice 1).
# Postgres remains the deployment target; SQLite keeps tests fast and hermetic.
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

TEST_DB = os.path.join(os.path.dirname(__file__), "test_vhs02.db")
try:
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
except OSError:
    pass  # locked by a previous run; drop_all below guarantees a clean slate
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
# Generous limits for the suite: every TestClient call shares one IP.
# Dedicated rate-limit tests override the limiter state directly.
os.environ["RATE_LIMIT_ANALYZE_IP"] = "10000"
os.environ["RATE_LIMIT_ANALYZE_USER"] = "10000"
os.environ["RATE_LIMIT_LOGIN_IP"] = "10000"
# Existing suite exercises the flag-off demo path (single shared demo user,
# pre-auth rows visible). Auth-on behavior has dedicated tests that override.
os.environ["AUTH_REQUIRED"] = "false"
# Test-only escape hatch so golden tests can pin the hour-of-day signal.
# Production keeps ALLOW_CLIENT_HOUR=false: client time never moves a verdict.
os.environ["ALLOW_CLIENT_HOUR"] = "true"

from fastapi.testclient import TestClient  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
client = TestClient(app)


def payment_payload(**overrides):
    base = {
        "analysis_type": "payment",
        "payment": {
            "amount": 150.0,
            "currency": "INR",
            "payee_id": "shop@grocery",
            "payee_name": "Corner Shop",
            "sender_balance": 5000.0,
            "note": "groceries",
            "channel": "upi",
            "merchant_category": "Groceries",
        },
    }
    base["payment"].update(overrides)
    return base
