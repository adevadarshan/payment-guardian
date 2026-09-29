# VH-S02 — Slice 4: Intelligence + Hardening + Integration

**Status:** Slice 4. Deterministic pipeline (payment/message/URL/QR) with
optional, disabled-by-default intelligence: a synthetic-data ML slot
(`MODEL_BACKEND=none` default) and a redacted advisory-only layer
(`ADVISORY_ENABLED=false` default) that can never change a verdict.
Real authentication (opaque bearer sessions, user-scoped data), server-side
rate limiting, configuration hardening, and a Docker Compose demo stack.

**Honest capability statement:** risk scores come from deterministic rules;
the ML model (when enabled) approximates those rules on synthetic data and
adds no independent fraud knowledge (`backend/ml/EVAL.md`); advisory text is
guidance, never a verdict. No accuracy claims are made anywhere in this repo
except the synthetic-eval numbers in `EVAL.md`, clearly qualified.

Behaviour inspired by the SentinelPay reference project (`../sentinelpay-main/`,
read-only — nothing is copied from it, and it is never a build dependency).
Credit: SentinelPay by Shaurya Naik and Siddhant Kerkar
(https://github.com/ShauryaNCode/sentinelpay, unlicensed — clean-room reimplementation).

## Run it (clean machine)

### Backend
```powershell
cd backend
pip install -r requirements.txt
pip install -r requirements-dev.txt
Copy-Item .env.example .env   # edit DATABASE_URL for Postgres, or keep SQLite
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Postgres target: `DATABASE_URL=postgresql+psycopg2://postgres:password@localhost:5432/vhs02`
SQLite fallback (tests + local runs without Postgres): `DATABASE_URL=sqlite:///./vhs02.db`

### Frontend
```powershell
cd web
npm install
npm run dev     # Vite proxy forwards /api to http://localhost:8000
```
Open http://localhost:5173 → redirects to `/login`. Seed demo accounts first:
`python backend/scripts/seed.py` (uses `DEMO_EMAIL`/`DEMO_PASSWORD` from env),
or run with `AUTH_REQUIRED=false` for the single-user local path.

### Docker Compose (demo stack)
```powershell
docker compose up --build     # db + api (migrates on start) + web on :80
python backend/scripts/seed.py  # against the composed API's database
```
See `DEMO_SCRIPT.md` for the timed demo. Recording the backup video and
securing venue hosting are manual final-demo tasks.

### Tests
```powershell
cd backend; python -m pytest -q        # SQLite-backed, hermetic
cd backend; python -m ruff check app tests
cd web; npx tsc --noEmit; npx vitest run; npm run build
```

## What's here
- `backend/` — FastAPI app, 24-category registry, deterministic payment analyzer
  (`pipeline/rules.py`, `pipeline/thresholds.py`, `analyzers/payment_analyzer.py`),
  message/URL/QR analyzers, normalization + fusion + explanation pipeline
  (`pipeline/normalize.py`, `signals.py`, `fuse.py`, `explain.py`, `run.py`),
  scans + hash-chained audit_log + `qr_seen`, Alembic `0001`–`0002`,
  pytest suite (golden corpora, units, parity, determinism, upload hardening,
  seen semantics, chain tamper).
- `web/` — six SentinelPay-structure pages (Login/Transaction/Result/Dashboard/History/Audit),
  gauge + reasons + safe-action + evidence + seen-badge + advisory-note components,
  session context, Recharts pie/histogram, typed API client, Vitest suite.
- Auth, rate limiting, ML slot, and advisory live behind flags documented in
  `backend/.env.example` (all safe defaults: required auth, no model, no advisory).

## QR upload limits (Slice 3)
Images ≤ 5 MB with PNG/JPEG/WEBP/GIF magic bytes and ≤ 12 MP decoded pixels;
anything else is rejected (413/422) or degrades to `unable_to_verify` — never a
500. Client preview decode (`jsqr`) is convenience only; the server re-decodes
every upload and its result is authoritative. Full payloads live in
`result_json` only when `STORE_QR_PAYLOADS=true` and never enter logs; audit
records carry the hash prefix + class only.

## Demo/local balance semantics (Slice 2)
"Make Payment" on the Result page is explicitly demo/local behaviour: it deducts
the analysed amount from a `localStorage` session balance (`vhs02-balance`),
seeded from the analysed `sender_balance` on first result view. MEDIUM/HIGH
verdicts require confirmation first; SAFE pays immediately. No money moves and
no server-side ledger exists — a real ledger, if ever needed, belongs
server-side and is out of scope.

## What's not here (by design)
Real-time threat feeds, DNS/WHOIS/fetching, visual QR forensics, push/email,
mobile app, signup UI, production TLS hosting. The product advises; it never
moves money.

## Third-party licences (summary)
FastAPI/uvicorn/SQLAlchemy/pydantic (MIT/BSD-family), XGBoost-free runtime —
ML is optional via `requirements-ml.txt` (scikit-learn BSD-3, joblib BSD-3);
`psycopg2-binary` (LGPL-3 with binary exception); React (MIT);
`argon2-cffi` (MIT); OpenCV headless (Apache-2.0). No SentinelPay source or
model artifact is used; behaviour is clean-room reimplemented (see header).
