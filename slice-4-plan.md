# Slice 4 Implementation Plan — Intelligence + Hardening + Integration

**Status:** PLAN ONLY — nothing implemented. No source files modified.
**Plan date:** 2026-09-29
**Governing document:** `D:\New folder (3)\sentipay\migrationrun.md` §7 (Slice 4), §§8–13, Appendix B.
**Prior plans:** `vh-s02/slice-2-plan.md` (incl. amendments A1–A4), `vh-s02/slice-3-plan.md` (incl. 7 amendments).
**New project:** `D:\New folder (3)\sentipay\vh-s02\`
**Reference (read-only):** `D:\New folder (3)\sentipay\sentinelpay-main\`
**Restore point:** Slice 3 (75 backend + 23 frontend tests green; contract `pipeline_version: "slice-3"`; migrations `0001`, `0002`).
**Final slice:** there is NO Slice 5. Deferred items stay deferred, documented in §24/§28.

## 1. Objective

Complete the migrated system: layer honest, optional intelligence (validated-or-absent ML, redacted advisory-only LLM) on top of the deterministic Slice 3 pipeline without changing its verdicts; add real authentication with user-scoped data, server-side rate limiting, and configuration hardening; prove the stack on PostgreSQL via Docker Compose; and leave the product demo-ready with seeded data, a rehearsed script, and a recorded backup. No UI redesign, no new pages, no new product features.

## 2. Current Slice 3 State

Verified by reading the actual code (not from reports).

### 2.1 Backend (`vh-s02/backend/`, 75 pytest collected)
- `app/pipeline/{normalize,signals,fuse,explain,run,rules,thresholds}.py` — pure deterministic pipeline; `run.analyze_request()` is the single orchestration entry for all four types; thresholds 35/75 from config; `ALLOW_CLIENT_HOUR=false` default (server-trusted hour).
- `app/analyzers/{base,payment,message,url,qr}_analyzer.py` — four analyzers emitting `Signal`s; payment math unchanged since Slice 2 (10 golden cases green unmodified).
- `app/schemas/analyze.py` — discriminated `AnalyzeRequest` (payment/message/url/qr + optional `payment_context`); full `AnalysisResult` (reasons/signals/evidence incl. `parsed_qr`/`payload_class`/`qr_decode`, seen, action, advisory-always-disabled, model-backend-none, `payment_summary`).
- Routes: `POST /api/analyze`, `GET /api/categories|scans|scans/{id}|stats|audit|health`, `POST /api/audit/verify`; stable 422/413/500 envelopes; **no auth, no rate limiting, no required secrets**.
- `app/db/models.py` — `scans` (8 payment cols, `result_json`), `audit_log` (hash chain), `QrSeen`; migrations `0001_initial`, `0002_qr_seen`.
- `app/data/risky_hosts.json` — 5 curated hosts, commented as demo heuristics (indicator, never proof).
- `requirements.txt` (8 pins incl. `opencv-python-headless==5.0.0.93`, `psycopg2-binary`) + `requirements-dev.txt` (+`qrcode[pil]`); **no sklearn, no auth, no rate-limit deps**.
- `.env.example` — SQLite default, `MODEL_BACKEND=none`, QR caps, `STORE_QR_PAYLOADS=true`, `PIPELINE_VERSION=slice-3`.
- Tests: 75 passing (golden payment/message/url, benign corpora, normalization, discriminated union, pipeline identity/determinism/composition, QR classification/UPI/routing/upload/authority/seen/NEW≠SAFE, persistence, audit tamper, parity).

### 2.2 Frontend (`vh-s02/web/src/`, 23 Vitest, `tsc` clean, `vite build` ok)
- Six routes behind a **demo-session `localStorage` guard** (`LoginPage` hardcoded demo creds — the thing Slice 4 replaces); `TopBar`; frozen token CSS.
- `TransactionPage` (Payment/Message/Link/QR modes, gates, 5s verify poll + breach dialog), `ResultPage` (gauge, reasons, safe action, evidence, seen badge, demo Make-Payment), `DashboardPage` (stats + Recharts pie/histogram + by-type row + alerts + feed), `HistoryPage` (level+type server chips), `AuditPage` (chain list, labels incl. `QR_SEEN`, verify, export, 10s refresh).
- `api/client.ts` — typed `ApiError` union **already includes** `unauthorized` and `rate_limited` kinds (forward-compatible with Slice 4 codes).
- Deps: react, react-router-dom, recharts, jsqr. No auth/session code, no advisory rendering, no model indicator.

### 2.3 Housekeeping noted during inspection
- No `ml/`, `llm/`, `auth/`, `users`, sessions, rate limiter, Dockerfile/compose/CI exist — greenfield, nothing to remove.
- `main.py` CORS: env allowlist (localhost) + `Authorization` header already allowed (harmless pre-auth; required for Slice 4 bearer tokens).
- `sentinelpay-main/` at 164 files, untouched; no `.pkl` referenced anywhere in `vh-s02/`.

## 3. Slice 3 Invariants

Release gates — each has an existing test that must stay green unmodified (named extensions only):

1. All four input types score through `run.py` with ordered reasons, evidence, type-aware actions.
2. Deterministic scoring: identical inputs → identical verdict fields (clock/randomness excluded).
3. Payment regression: all 10 Slice 2 goldens satisfy the §3.1 behavioral identity (score/level/reasons/signals/evidence/action/validation).
4. QR authority: server re-decode wins; client payload ignored when image present; hostile uploads → 413/422/`unable_to_verify`, never 500.
5. Seen semantics: first `new` + row, rescan `previously_seen` ×2, variants share hashes, corrupt → no row; NEW≠SAFE triple-enforced.
6. Non-SAFE verdicts always carry ≥1 reason; `advisory.status` stays `disabled` until §7 lands.
7. Single hash-chained audit log; tamper detected at the exact entry; `QR_SEEN` logged once per hash.
8. Six routes, navigation, token values, information hierarchy unchanged.
9. Thresholds 35/75 server-owned; `MODEL_BACKEND=none` disclosed; no accuracy claims anywhere.

## 4. Slice 4 Requirements from migrationrun.md

Bound from §7 (+§8 sequencing, §9 verification, §13 DoD, Appendix B non-goals); nothing beyond them is in scope:

- Unified pipeline already exists — Slice 4 keeps it, adds the optional ML signal slot.
- `ml/registry.py` (strict features, version, SHA-256 checksum; load failure never blocks startup), `ml_analyzer.py` (bounded signal), `ml/artifacts/` only with upstream permission+provenance **or** own `train.py` on licensable data with published golden-set evaluation; default `MODEL_BACKEND=none` is an acceptable honest outcome.
- `services/advisory.py` (provider-agnostic, disabled default, timeout, graceful degradation, cost/latency cap, redacted signals-only input unless a human approves otherwise); advisory-only output that cannot change score/level/reasons (invariant test).
- Auth: `users` + `0003_users` (nullable `user_id` on scans/audit_log + indexes), Argon2/bcrypt hashing, short-lived access + refresh, login/logout/me, env-seeded demo accounts, React guard + session context, user-scoped queries, 404/403 authorization, audit scope per decision D5.
- Server validation on every endpoint (largely exists; extend to new auth/ML/advisory paths); server rate limiting (~10/min on analyze, 429 + `retry_after`); CORS allowlist (exists — verify + lock); env-only secrets with loud failure; internal-only HMAC; upload final pass; audit verify/export hardening; browser-only opt-in fingerprinting (already the design — keep, disclose).
- E2E suite, Dockerfile + compose + static frontend path, seed script, timed demo script + backup video, README (run/architecture/honest capabilities/credit/licences).
- Boundary §7.3: no redesign, no new pages, no animation work, no live reputation, no server-side fetching, no real payments, no mobile app.
- DoD §7.7 items map to §§19/27/31 of this plan; rollback is flag-gated + additive migrations.

## 5. Intelligence Architecture

Deterministic Slice 3 pipeline remains the source of truth. Intelligence is a sidecar, never a replacement:

```
analyze_request()
  ├─ deterministic core (unchanged): normalize → analyzers → fuse → classify
  │     → score/level/reasons/signals  (AUTHORITATIVE, always present)
  ├─ ml_analyzer (optional, flag + artifacts + checksum): bounded extra Signal(s)
  │     → fused ONLY through the same fuse(); contribution capped (±15 total);
  │       disclosed in signals[] + model{backend,version}
  ├─ explain (unchanged ordering) → reasons/evidence/action
  └─ advisory_service (optional, flag + provider): narrative text → advisory{}
        (never touches score/level/reasons/signals; runs AFTER verdict built,
         timeout-bounded, failure → status timeout/error, request still 200)
```

Rules: (a) with ML off and advisory off, responses are structurally identical to Slice 3 plus `pipeline_version: "slice-4"`; (b) with ML on, the optional ML stage may only add a bounded `ml.risk` contribution through the same `fuse()` — ML never selects `risk_level`, and the final `risk_level` is always server-derived from the final fused score via the existing `classify()` thresholds; every score shift is traceable to named `ml.*` signals; (c) advisory output appears only in `advisory{}`; (d) any intelligence failure degrades to disabled-status, never to 500.
- **Current:** no ML/advisory code paths exist.
- **Required:** the layering above, with kill-switches (`MODEL_BACKEND`, `ADVISORY_ENABLED`) defaulting off.
- **Approach:** add, don't rewire — core functions keep signatures; `run.py` gains two clearly-marked optional stages.
- **Verification:** invariant tests (§19: advisory-never-changes-score across all four types; ML-cap test; both-off structural equality with Slice 3 shape).

## 6. ML Plan

- **Provenance/licensing (normative):** the quarantined upstream `.pkl` files are NEVER loaded, copied, or referenced — no permission exists and none is assumed. The only trainable path is `backend/ml/train.py` generating data we own: synthetic transactions/messages/URLs/QR-feature rows derived from our golden corpora + programmatic variations, written to `backend/ml/data/synthetic_v1.jsonl` with a provenance header (generator version, seed, sources). No third-party dataset is introduced in Slice 4.
- **Feature schema (versioned):** `FEATURES_V1` = per-analysis numeric vector assembled ONLY from already-computed analyzer outputs (e.g. for payment: amount_log, drain_ratio, tier_points/50, category_points/25, hour_onehot(2), note_urgent?, note_info?, payee_unverified? — fixed order, fixed length, documented in `ml/features.py`). Labels: golden band mapped SAFE→0, MEDIUM/HIGH→1 (binary). Schema version string stored with the artifact; loader rejects mismatched versions loudly.
- **Training/inference boundary:** `train.py` (offline, dev-only) → writes `ml/artifacts/{model.joblib, metadata.json{version, feature_schema, sha256, trained_at, eval}}`. Inference (`ml/registry.py` + `ml_analyzer.py`) loads read-only, verifies SHA-256 + schema version, and emits at most one bounded signal (`ml.risk`, contribution clamped to ±15, observation cites model version). Training code never runs inside the API process.
- **Artifact loading/validation:** registry loads at startup when `MODEL_BACKEND != "none"`; missing dir, checksum mismatch, schema mismatch, or unloadable file → log error, fall back to `none`, API still starts (kill-switch, tested). `GET /api/health` reports `model_backend` truthfully (`none` vs `synthetic-v1`).
- **Unavailable-model behavior:** default `MODEL_BACKEND=none`; every verdict discloses `model.backend`; UI shows "Model: off". Enabling requires explicit env + present valid artifacts.
- **No fabricated accuracy:** metrics come ONLY from the committed evaluation: `train.py` splits synthetic data into train vs held-out evaluation sets (fixed seed, documented split ratios in `EVAL.md`), and reports metrics on the held-out set ONLY. The golden corpora remain regression/smoke tests — because training variations derive from golden examples, goldens must NOT be treated as the primary performance evaluation set. `EVAL.md` clearly discloses the synthetic-data methodology, the exact split, and this limitation. README/UI copy is restricted to those numbers with the "synthetic data" qualifier; the pre-demo sweep (§19) greps for violations.
- **Dependencies:** new optional `requirements-ml.txt` (`scikit-learn`, `joblib`, versions pinned at implementation; core `requirements.txt` untouched). Algorithm: logistic regression (linear, inspectable, tiny). If sklearn proves problematic in this environment, fallback is shipping interface-only with `none` default (migrationrun-allowed honest outcome) — decided before writing training code, not after.
- **Verification:** `test_ml_registry_integrity` (missing dir/checksum/schema mismatch → `none`, startup unblocked), `test_ml_bounded_signal` (contribution within cap; golden bands move at most one level and only on documented cases — or move not at all), `test_ml_disabled_default`, golden corpora green in both modes.

## 7. LLM Advisory Plan

- **Provider abstraction (minimal, as required):** `app/services/advisory.py` defines a `Provider` protocol (`generate(redacted_input, *, timeout_s) -> {text|error}`) with exactly two implementations: `StubProvider` (deterministic template guidance assembled from the verdict's reasons — works offline, default) and `HttpProvider` (generic OpenAI-compatible POST to `ADVISORY_ENDPOINT` with `ADVISORY_API_KEY`, only when `ADVISORY_ENABLED=true` and both env vars set). No SDK dependencies.
- **Input/output contract:** provider receives ONLY `{analysis_type, risk_level, reason_codes+observations, seen_status, top_evidence_kinds}` — never raw message text, URLs, QR payloads, names, or amounts. Enforced by a redaction constructor + a test asserting banned substrings absent from captured provider input. Output: `{status, provider, text (≤600 chars, truncated)}`.
- **Timeout/error behavior:** hard timeout (default 8s, env-overridable); timeout → `status: "timeout"`; provider error → `status: "error"`; disabled → `status: "disabled"`. All paths return HTTP 200 with the deterministic verdict intact.
- **Failure isolation:** advisory runs only AFTER the deterministic verdict is fully built AND persisted; exceptions are caught at the service boundary; advisory output is attached to the response object only — an advisory timeout/error must never modify the persisted verdict, score, level, reasons, or signals. Advisory latency is logged but never blocks the response contract (run synchronously with timeout for Slice 4 simplicity — no queues).
- **Disclosure:** `advisory{status, provider ("stub"|endpoint host|None), text?}`; UI renders it in a labelled "Advisory (not a verdict)" note; `GET /api/health` reports advisory mode.
- **Privacy:** D6 default holds (signals-only). Raw-text passthrough requires a human yes (Open Decision 4) and is otherwise a scope failure.
- **Verification:** `test_advisory_never_changes_score` (stub returning extreme text across all four types → verdict fields field-identical to the disabled run), timeout/error/disabled tests, redaction test, cost guard (text length cap), frontend advisory-note test.

## 8. Authentication/User Plan

- **Minimal model (per migrationrun):** `users(id uuid PK, email unique, password_hash, display_name, is_demo, created_at)` + `sessions(token_hash PK, user_id FK, expires_at, created_at)` + nullable `user_id` (+indexes) on `scans` and `audit_log`. Opaque bearer tokens (`secrets.token_urlsafe`, SHA-256 stored, never logged). Access 60 min, refresh rotation 7 days (single `sessions` table with `kind` + `replaces` chain — kept minimal, documented).
- **Hashing:** `argon2-cffi` (new required dep — server-side only, wheels available; chosen over bcrypt for modern API + no 72-byte limit surprises).
- **Endpoints:** `POST /api/auth/login` (email+password → access+refresh, 401 on bad creds with identical timing), `POST /api/auth/refresh`, `POST /api/auth/logout` (revoke), `GET /api/auth/me`. Validation shapes + 422 envelope as everywhere else.
- **Ownership:** every scan/audit write stamps `user_id` (nullable for pre-auth rows); reads filter by caller (`GET /api/scans|stats|audit`); cross-user id access → 404 (not 403, to avoid id oracle — document the choice); audit verify checks the global chain but the response only exposes entries the caller may see... decision: verify returns global validity + counts only (no per-entry leak), keeping D5's "global chain, user-scoped visibility".
- **Demo usability:** `AUTH_REQUIRED` flag (default true; local `.env.example` sets false with comment). `AUTH_REQUIRED=false` is allowed ONLY when `APP_ENV` is `development`/local — production configuration with auth disabled fails startup loudly, covered by a dedicated safety-invariant test. When false, requests run as the seeded demo user (no login wall, demo script unchanged). Seeded demo accounts come from env (`DEMO_EMAIL`, `DEMO_PASSWORD`), never hardcoded. No signup endpoint (explicit non-goal).
- **Frontend:** `state/session.tsx` (token storage, login/logout, refresh-on-401-once), `api/auth.ts`, route guard switched from `localStorage` demo flag to session (same redirect UX, same Login look), 401/429 error states. No profile pages, no password-change UI.
- **Verification:** auth flow tests (login/bad/expired/revoked/refresh), ownership isolation tests (user B cannot read user A's scan → 404; stats/audit scoped), guard tests, flag-off demo path test.

## 9. Rate Limiting Plan

- **Smallest practical:** in-memory sliding-window dependency (no Redis — single-instance demo/compose; documented limitation), applied to `POST /api/analyze` (per-IP 10/min unauthenticated; per-user 60/min authenticated) and auth endpoints (per-IP 5/min on login).
- **Contract:** 429 + existing envelope shape with `code: "rate_limited"` + `Retry-After` header + `retry_after` seconds in details. Client already handles `rate_limited` kind (§2.2) — wire it to the existing wait UI.
- **Implementation:** `app/security/ratelimit.py` (pure window logic, injectable clock for tests) + FastAPI dependency; state in process memory; multi-worker skew documented (compose runs `--workers 1` for the API).
- **Verification:** burst-over-limit → 429 + header; window slide; per-user vs per-IP buckets independent; normal traffic unaffected (golden suite runs under limits — set test-mode generous limits via env, documented).

## 10. Security Hardening

Item-by-item (current → required → verify):
- **CORS:** allowlist already from env — add test asserting foreign `Origin` gets no ACAO header and allowed origin works; remove nothing (the `Authorization` header allowance stays, now actually used).
- **Secrets/config:** no new application secret is introduced — password hashing is straightforward Argon2id (no custom pepper; migrationrun.md does not require one) and opaque tokens use `secrets.token_urlsafe`. Production hardening is enforced structurally instead: startup with `APP_ENV=production` fails loudly unless `DATABASE_URL` is non-SQLite and `CORS_ORIGINS` is explicitly set (non-default), tested. All secrets that do exist (demo seed credentials, advisory key) are env-only, `.env` gitignored (already), `.env.example` documents shapes with placeholder values only. No secret/host literals in code or bundle (existing scan extended to new files).
- **Trusted hosts:** `TrustedHostMiddleware` allowlist from env, enabled when `APP_ENV=production` (localhost + configured hosts); verified by test with spoofed `Host`.
- **Request-size limits:** `Content-Length` guard middleware on `/api/*` (8 MB default, env-overridable) → 413 envelope; Pydantic field caps stay authoritative per-field.
- **QR/image handling:** final pass — re-encode decoded image server-side before OpenCV detect (normalizes polyglots), confirm pixel/size/magic tests still green, log-redaction rule re-asserted (no payload/token/message text at INFO+).
- **Error leakage:** generic 500 envelope (`server_error`, no traceback) with `APP_ENV=development` stack logging server-side only; test asserts no `traceback`/`File "` strings in 500 bodies.
- **Security headers:** `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer` via middleware; tested.
- **Fingerprinting:** unchanged browser-only design (already weak-signal + disclosed); no new collection in Slice 4.
- **HMAC:** explicitly excluded. There is no Slice 4 service-to-service architecture requiring request signing, so no HMAC utility ships — no unused future infrastructure. (Rationale recorded here so a reviewer does not re-add it: shared secrets cannot live in the browser, and no internal caller exists.)
- **Validation:** extend the one-model-per-contract rule to auth/stats/scan-detail inputs (already true for analyze); add `test_unknown_field_rejected` (Pydantic `extra="forbid"` audit across request models — implement by setting forbid on new auth models and documenting that analyze models stay permissive-for-back-compat... decision: analyze models gain `extra="forbid"` too, since contract tests already pin exact shapes — verify against golden suite).

## 11. PostgreSQL Plan

- **Current:** SQLite default local/test; PG URL supported by SQLAlchemy layer; `psycopg2-binary` pinned; JSON columns (portable), no PG-only types; hash-chain math is Python-side (DB-agnostic).
- **Production path:** `docker-compose.yml` runs `postgres:16-alpine` with a volume; API entrypoint runs `alembic upgrade head` then uvicorn `--workers 1`; `DATABASE_URL` points at `db:5432`.
- **Migration verification:** `0001→0002→0003` upgrade clean on scratch PG; downgrade chain `0003→0001` verified; `qr_seen` PK/FK/CHECK enforced on PG (SQLite-tolerated differences documented, not depended upon).
- **Behavioral parity:** hash-chain verify, seen lookup/bump, golden payment case, and audit tamper check re-run against PG via `TEST_POSTGRES_URL`-gated tests (`tests/test_postgres_parity.py`, skipped when unset) — same assertions as the SQLite suite on a scratch database.
- **Indexes:** 0003 adds `user_id` indexes on scans/audit_log (migrationrun-required); verify `EXPLAIN` uses them on PG (smoke-level, documented output).
- **Old rows:** Slice 1/2/3 rows read unchanged (contract additive-only rule); SQLite local dev stays the default documented path.
- **Unknown:** no Docker daemon is available in this environment (verified during Slice 3) — compose/PG verification is environment-dependent (see §28.6). Core Slice 4 implementation and testing must remain fully verifiable without Docker: if Docker is unavailable, Docker/Compose/PG verification is recorded as environment-blocked, never as an implementation failure. Docker/Compose/PG verification is required whenever the environment supports it.

## 12. Docker/CI Plan

- **Minimal, venue-oriented (migrationrun requires compose, not deployment infra):**
  - `backend/Dockerfile` — `python:3.12-slim`, install `requirements.txt` (+`requirements-ml.txt` optional build-arg, default off), copy app, entrypoint `scripts/docker-entrypoint.sh` (`alembic upgrade head` → exec uvicorn `--host 0.0.0.0 --port 8000 --workers 1`).
  - `web/Dockerfile` — node build stage (`npm ci && npm run build`) → nginx stage serving `dist/` with `/api` reverse-proxy to `api:8000`; static `VITE_API_BASE_URL=/api` baked at build.
  - `docker-compose.yml` (repo root of `vh-s02/`) — `db` (postgres:16-alpine, named volume, healthcheck `pg_isready`), `api` (build backend, env_file, depends_on healthy db), `web` (build, ports `80:80`, depends_on api). No registry, no TLS, no orchestrator.
  - `scripts/seed.py` — idempotent: env-seeded demo users + ~12 mixed scans (all four types, all three levels) so the dashboard has content on arrival.
- **CI (`.github/workflows/ci.yml` — minimal):** jobs `backend` (pip install reqs, `pytest -q`, `ruff check app tests`), `frontend` (`npm ci`, `tsc --noEmit`, `vitest run`, `vite build`), `compose` (docker build of both images; full `compose up` test gated on docker availability). No deploys, no secrets in CI beyond placeholders.
- **Verification:** `docker build` both images; `docker compose up` → health → seed → full demo script via composed URLs; teardown leaves no state (named volume documented for reset). Where Docker is unavailable, record compose/PG verification as environment-blocked (not a failure); the SQLite suite plus code review of the Dockerfiles still gate the slice.

## 13. Risky Host Maintenance

- **Provenance (stated, not changed):** `app/data/risky_hosts.json` is curated demo/test heuristic data with per-group source comments — explicitly NOT live threat intelligence (file header + README section).
- **Update mechanism:** PR editing the JSON + updating `test_golden_url.py` expectations in the same commit; CI runs the URL corpus.
- **Validation:** new `test_risky_hosts_schema.py` — ≤50 entries, valid lowercase hostnames, sorted, de-duplicated, each with a `reason` string; loader ignores malformed file with a startup warning (never crash).
- **Review process:** maintainer ack required (documented in README); entries must cite pattern-origin (e.g. "observed pattern: <brand>-<action>.top"), never a real victim or unconfirmed report.
- **Test behavior:** one seeded host keeps its golden case; a match remains an indicator (+30) with observation wording unchanged ("indicator, not proof").
- **Unknown:** none — mechanism is fully specified.

## 14. Visual QR Forensics

**Not included.** migrationrun Appendix B explicitly excludes "visual QR or logo forensics" and §7.3 confirms the boundary. Slice 4 therefore ships: no logo detection, no pixel-tamper analysis, no visual-authenticity claims. The `unable_to_verify` path remains the honest answer for undecodable images. Enforced by tripwire §30.7.

## 15. API Contract

Additive-only (migrationrun sequencing rule §8.2). Current → Slice 4:

- `POST /api/analyze` — unchanged shape; gains `advisory{status ok|timeout|error, provider, text?}` when enabled (else `disabled` as today) and `model{backend: none|synthetic-v1, version?}` when enabled. New error code `rate_limited` (429). Authenticated requests stamp `user_id` (invisible in response).
- `GET /api/health` — additive: `+ auth_required: bool, advisory: "disabled"|"stub"|provider-name, ml_artifacts: bool`. Existing keys unchanged.
- `GET /api/scans|scans/{id}|stats|audit`, `POST /api/audit/verify` — shapes unchanged; now user-scoped when `AUTH_REQUIRED` (same shapes, filtered rows).
- New: `POST /api/auth/login|refresh|logout`, `GET /api/auth/me` (schemas in §8 shapes).
- Contract tests assert old clients still validate (frozen example payloads from Slice 3 replayed byte-for-response-shape).
- Frontend types gain `Stats` (unchanged), `AuthState`, `AdvisoryInfo`, `ModelInfo` display fields — additive only.

## 16. Database Changes

**One migration: `0003_users`. Nothing else. Existing migrations untouched.**

```python
# alembic/versions/0003_users.py (down_revision = "0002_qr_seen")
# - CREATE TABLE users(id VARCHAR(36) PK, email VARCHAR(320) UNIQUE NOT NULL,
#     password_hash TEXT NOT NULL, display_name VARCHAR(120),
#     is_demo BOOLEAN NOT NULL DEFAULT false, created_at TIMESTAMPTZ NOT NULL)
# - CREATE TABLE sessions(token_hash CHAR(64) PK, user_id VARCHAR(36) NOT NULL
#     REFERENCES users(id) ON DELETE CASCADE, kind VARCHAR(16) NOT NULL,
#     expires_at TIMESTAMPTZ NOT NULL, created_at TIMESTAMPTZ NOT NULL);
#     CREATE INDEX ix_sessions_user_id ON sessions(user_id)
# - ALTER TABLE scans ADD COLUMN user_id VARCHAR(36) NULL
#     REFERENCES users(id) ON DELETE SET NULL; CREATE INDEX ix_scans_user_id
# - ALTER TABLE audit_log ADD COLUMN user_id VARCHAR(36) NULL
#     REFERENCES users(id) ON DELETE SET NULL; CREATE INDEX ix_audit_user_id
# downgrade(): drop indexes/columns/tables in reverse (data loss documented).
```

- Compatibility: purely additive; pre-auth rows keep `user_id NULL` and remain readable; downgrade restores the Slice 3 schema exactly.
- SQLite: FKs advisory-only (pragma-dependent) — behavior tests assert service semantics, not FK cascades; PG enforces all constraints (parity test).
- Rollback: `alembic downgrade -1` + code revert; reverting code alone leaves new columns harmlessly null.
- Irreversible decisions flagged: `users.id` UUID-string PK format; token model (opaque, §27.2); nullable-not-required `user_id` (pre-auth history preserved by design).

## 17. Frontend Changes

Additive only; routes, navigation, tokens, hierarchy frozen:

- `state/session.tsx` (new) — session context (tokens in memory + refresh, login/logout, me); `api/auth.ts` (new) — typed auth calls.
- `LoginPage.tsx` (logic-only edit, same look) — real login against API; demo creds prefilled from display text only when the server seeds them (no hardcoded passwords in source); error states for 401/429.
- `App.tsx` guard → session-based (same redirect UX).
- `ResultPage.tsx` — one status line: `Model: off|synthetic-v1 · Advisory: disabled|available` + `AdvisoryNote` component (new, small, visually labelled "Advisory — not a verdict", renders only when `advisory.status == "ok"`).
- `AuditPage.tsx` — unchanged (verify/export already wired; user-scoping is server-side).
- Transaction/Dashboard/History — unchanged except 429 wait-state surfacing through the existing `ApiError` path (already typed; wire to the existing warning banner).
- No new pages, no new nav items, no new libraries (recharts/jsqr already present suffice).

## 18. Incremental Implementation Sequence

Small vertical increments; each ends with focused tests + full Slice 3 regression + tripwire check before continuing:

1. **Config/secrets hardening** — production guards (non-SQLite URL, explicit CORS, auth-flag safety), TrustedHost (prod-gated), security headers, request-size guard, 500 envelope, log-redaction rule + tests. No behavior change otherwise.
2. **Rate limiting** — in-memory windows, 429 contract, client wait-state wiring, tests (burst/slide/scopes).
3. **Auth + users** — models, `0003`, hashing, sessions, four endpoints, guard, user-scoping, seed script, frontend session + login logic, ownership tests. (`AUTH_REQUIRED` default true; local example false.)
4. **ML slot** — registry + synthetic `train.py` + `EVAL.md` + `ml_analyzer` + disclosure + both-modes tests. Cut to interface-only if time runs short (pre-agreed fallback, still shippable).
5. **Advisory** — adapter + stub (+optional HTTP provider), redaction, timeout/error, invariant, UI note + indicator.
6. **Postgres + Docker/CI + demo readiness** — compose files, entrypoint/seeding, PG parity tests (where docker exists), CORS/security tests, `DEMO_SCRIPT.md` + README, full verification sweep. (Recording the backup video and securing venue hosting are manual final-demo tasks, not coding implementation.)

## 19. Test Plan

Backend (`pytest`, SQLite-hermetic unless noted):
1. Full Slice 3 suite green unmodified (31→75 files untouched; new files only).
2. `test_ml_registry.py` — missing dir/checksum/schema mismatch → `none`, startup unblocked; valid artifacts → version disclosed.
3. `test_ml_signal.py` — contribution within ±15 cap; golden bands documented (move ≤1 level or not at all); `none`-mode structural equality.
4. `test_advisory.py` — never-changes-score across 4 types (extreme stub text), timeout/error/disabled paths, redaction (banned raw substrings absent from captured provider input), length cap.
5. `test_auth.py` — login/bad/expired/revoked/refresh/logout/me; 401 shapes; timing-similarity smoke for bad creds (documented, not strict).
6. `test_ownership.py` — cross-user 404s, stats/audit scoping, pre-auth NULL rows visible only with auth off.
7. `test_rate_limit.py` — burst→429+header, window slide, per-IP vs per-user independence, clock-injectable windows.
8. `test_cors_security.py` — foreign origin refused, allowed origin works, security headers present, TrustedHost spoof rejected (prod mode), 500 body leak-free, unknown-field rejection, production-guard startup failures (sqlite-URL and default-CORS under `APP_ENV=production`), `AUTH_REQUIRED=false` under production fails startup.
9. `test_postgres_parity.py` — skipped unless `TEST_POSTGRES_URL` set: migrations, golden payment case, chain tamper, seen bump, old-row read. A skip is recorded as environment-blocked verification, not a pass of untested behavior.
10. `test_migrations.py` — 0001→0003 upgrade clean on scratch SQLite; 0003→0001 downgrade clean; `qr_seen`/`users` present after full upgrade.
11. `test_risky_hosts_schema.py` — per §13.
12. `test_contract_frozen.py` — Slice 3 example payloads replayed; response shapes superset-compatible.
Frontend (Vitest): session login/logout/guard/401/429 states; advisory note + model indicator rendering; audit/dashboard/history unchanged-green; `tsc`, `vite build`.
CI-equivalent locally: `pytest -q`, `ruff check app tests`, `tsc`, `vitest run`, `vite build`, both `docker build`s (where docker exists).

## 20. Manual Verification Plan

Record output + screenshots (adapted from migrationrun §7.6):

1. Full demo script timed on the demo machine, offline except local API (or compose network): 3 payment levels, 1 message, 1 URL, 1 QR, 1 duplicate-QR, 1 chain-tamper. (Executing/recording the video is a manual final-demo task; the coding agent's obligation is the script + a runnable stack.)
2. Auth: logged-out deep-link to `/dashboard` → login; two demo users → isolated histories; bad password → error, no oracle.
3. Rate limit: rapid submits → client wait notice + API 429 with `retry_after`.
4. CORS: foreign-origin fetch refused; configured origin works.
5. Advisory: on → labelled note, score identical to off-run; off → fully functional.
6. ML: `none` → `backend: none` disclosed; enabled (if artifacts built) → version disclosed, checksum verified, goldens hold.
7. Tamper via SQL → red dot + dialog naming entry → restore → green; export downloads.
8. Upload abuse set (20 MB, wrong MIME, non-image, pixel-bomb) → clean rejections, no 5xx.
9. `docker compose up` on a clean machine → seed → demo script passes (where docker exists; else documented environment-blocked skip with reason).
10. README-only fresh-environment walkthrough; pre-demo claim sweep (grep accuracy/performance language vs `ml/EVAL.md`).

## 21. Security/Privacy Review

- **Stays local:** raw message/URL/QR text, payloads, balances, password hashes, tokens (hashed), audit content, ML artifacts. Postgres volume is local; no telemetry added.
- **May leave the machine:** only via `HttpProvider` when explicitly enabled — and then only the redacted advisory input (level, codes, observations, seen status). Default path sends nothing anywhere (stub is in-process).
- **Never logged:** passwords, tokens, secrets, full QR payloads, raw message text, full URLs at INFO+ (allowlisted log fields for the analyze path; test asserts).
- **Credentials:** Argon2id-hashed (no custom pepper), opaque tokens hashed at rest; refresh rotation; demo seeds from env, never source.
- **Model/advisory data flow:** artifacts are local files; stub advisory is in-process; HTTP advisory is documented, flagged, and off by default.
- **Unknown:** venue network policy (assume offline → defaults already safe).

## 22. Files to Create

**Backend:** `app/ml/__init__.py`, `app/ml/registry.py`, `app/ml/features.py`, `app/ml/train.py`, `app/ml/EVAL.md`, `app/ml/artifacts/.gitkeep` (+generated `model.joblib`, `metadata.json` only when trained), `app/analyzers/ml_analyzer.py`, `app/services/advisory.py`, `app/security/__init__.py`, `app/security/auth.py`, `app/security/ratelimit.py`, `app/api/routes/auth.py`, `alembic/versions/0003_users.py`, `requirements-ml.txt`, `Dockerfile`, `docker-compose.yml` (repo root of vh-s02), `scripts/docker-entrypoint.sh`, `scripts/seed.py`, `.github/workflows/ci.yml`, tests: `test_ml_registry.py`, `test_ml_signal.py`, `test_advisory.py`, `test_auth.py`, `test_ownership.py`, `test_rate_limit.py`, `test_cors_security.py`, `test_postgres_parity.py`, `test_migrations.py`, `test_risky_hosts_schema.py`, `test_contract_frozen.py`.
**Frontend:** `state/session.tsx`, `api/auth.ts`, `components/AdvisoryNote.tsx`, tests for session/guard/advisory/429 paths.
**Docs:** `DEMO_SCRIPT.md` (timed script — the coding agent prepares the script and README instructions; recording the backup video and securing venue hosting are manual final-demo tasks for a human, and implementation must not block waiting for them).

## 23. Files to Modify

| File | Current | Change |
|---|---|---|
| `app/main.py` | routers, CORS, 422 envelope | + auth router, rate-limit dep wiring, TrustedHost (prod-gated), security headers, size guard, 500 envelope, lifespan model-preload attempt (non-blocking) |
| `app/config.py` + `.env.example` | slice-3 flags | + `AUTH_REQUIRED=true`, `ADVISORY_ENABLED=false`, `ADVISORY_*`, `MODEL_BACKEND=none`, `PIPELINE_VERSION=slice-4`, rate-limit knobs, TrustedHost list |
| `app/pipeline/run.py` | 4-type dispatch | + optional ML stage + advisory stage (both guarded, post-verdict) |
| `app/api/routes/analyze.py` | verdict→persist→audit | + attach advisory/model output, stamp `user_id`, enforce rate-limit dep |
| `app/repositories/scans.py`, `audit.py` | unscoped queries | + `user_id` filter params (None = all only when auth off) |
| `app/db/models.py` | Scan/AuditLog/QrSeen | + `user_id` cols (nullable+indexed), `User`, `Session` models |
| `app/api/routes/scans.py`, `stats.py`, `audit.py` | unscoped | auth dep + scoping; shapes unchanged |
| `web/src/pages/LoginPage.tsx` | demo-flag logic | real login logic, same look |
| `web/src/App.tsx` | demo guard | session guard, same UX |
| `web/src/pages/ResultPage.tsx` | verdict display | + model/advisory status line + `AdvisoryNote` |
| `web/src/api/analyze.ts`, `types.ts` | S3 types | + auth/advisory/model display types |
| `vh-s02/README.md` | Slice 3 runbook | Slice 4: compose path, auth, flags, honesty statement, licences |
| `backend/requirements.txt` | 9 pins | + `argon2-cffi` (auth) only; ML stays in `requirements-ml.txt` |

**Do not touch:** Slice 3 analyzers' scoring math, `rules.py`, `thresholds.py`, `categories.py` values, `audit_service.py` canonical form, `0001`/`0002`, token CSS, six routes, `gates.ts`, `lib/balance.ts`, golden corpora expectations.

## 24. Scope Boundaries

**In:** §§5–21. **Out (deferred past migration, must not leak):** new product features, UI redesign/polish, new pages/routes/nav, profile/password-change UI, signup, push/email, live reputation/DNS/WHOIS/fetching, visual QR forensics, real payment execution, mobile app, multi-bank/federation, Kubernetes/TLS/registries, monitoring stacks, analytics beyond existing dashboard, additional ML models/algorithms, embedding models, fine-tuning, dataset collection beyond synthetic, any Slice 5.

## 25. Risks and Mitigations

| # | Risk | Mitigation |
|---|---|---|
| 1 | Time overrun (auth + ML + advisory + compose in one slice) | §18 order (hardening → limits → auth → ML → advisory → compose); ML has a pre-agreed interface-only fallback; advisory stub is functional day one. |
| 2 | Synthetic ML proves little / invites overclaim | EVAL.md with disclosed methodology; UI shows "Model: synthetic-v1"; pre-demo claim sweep; default off. |
| 3 | Auth bugs lock out the demo | `AUTH_REQUIRED=false` local path tested; seeded accounts; flag-off fallback rehearsed. |
| 4 | In-memory rate limits mislead under workers | Single-worker compose + documented limitation; tests inject clocks, not sleeps. |
| 5 | Secret mishandling (seed storage, token handling) | Loud-failure production guards, `.env` gitignored, scan tests, documented rotation (change value + restart). |
| 6 | Scope leak into redesign/polish | §24 + tripwires; UI diffs limited to listed files. |
| 7 | Environment fragility (PG/docker unavailable here) | Compose verification marked environment-dependent; SQLite path kept green; seed script works on both. |
| 8 | Reference transcription (clean-room) | New code authored from this plan's normative lists; no upstream files opened. |

## 26. Rollback Strategy

- Branch `slice/4-hardening`; Slice 3 tag is the restore point (`git checkout slice-3` / `git revert <range>`).
- Flag-gated surfaces (`MODEL_BACKEND`, `ADVISORY_ENABLED`, `AUTH_REQUIRED`) — a bad deploy is a config change; all three default to safe (none/disabled/required... note: `AUTH_REQUIRED` defaults true; venue fallback is explicit false, rehearsed).
- `0003_users` additive (nullable cols + new tables); code revert leaves schema valid; `alembic downgrade -1` documented with data-loss note.
- Frontend additions are additive components/context; page edits revert cleanly.
- Worst case: restore Slice 3 tag; `sentinelpay-main/` never at risk.

## 27. Expensive-to-Reverse Decisions

1. **`users.id` UUID-string PK + opaque token model** — central to auth; changing to JWT/sessions-table-less later requires migration + client rework. Chosen for revocation simplicity and no crypto-in-client.
2. **Nullable (not required) `user_id`** — preserves pre-auth history forever; making it required later would orphan rows. Chosen deliberately (history continuity > strictness).
3. **ML feature schema `FEATURES_V1`** — frozen once artifacts ship; changes require retrain + version bump + dual support or migration. Loader rejects mismatches loudly by design.
4. **Advisory contract shape** (`advisory{status,provider,text}` + redacted input) — frontend and tests pin it; raw-text passthrough would be a contract + privacy break, hence human-gated.
5. **Compose topology** (db/api/web, single worker, entrypoint-migrates) — demo procedures and docs harden around it.
6. **Global chain + user-scoped visibility** (D5 default) — changing to per-user chains later forks history semantics.
7. **Risky-host "indicator, never proof" semantics** — upgrading to live reputation would be a product/legal change, not a config flip.

## 28. Open Decisions

Genuinely blocking (recommendations included; work proceeds on defaults if unanswered):

1. **Upstream licence response (D2):** assume none → synthetic-only ML. If permission arrives mid-slice, artifacts still require provenance review before use — no silent adoption.
2. **Demo runs with ML on or off (D3)?** Recommended: default off everywhere; enable `synthetic-v1` only for the recorded ML-verification run. Prevents overstating.
3. **Audit scope (D5):** recommended global chain + `user_id` attribution + user-scoped listing + global-only validity response. Confirm or choose per-user chains (heavier, breaks D5 demo story).
4. **Advisory raw-text passthrough (D6):** recommended NO (signals-only enforced + tested). A human yes reopens contract §15 and §21.7.
5. **Advisory provider for the demo (D7):** recommended stub default; optional generic-HTTP provider configured only with explicit env. Confirm no vendor SDK may be added.
6. **Venue hosting (D12):** recommended local compose primary; cloud backup undecided — needs a human owner + account before Slice 4 ends. Venue hosting decisions and execution are manual final-demo tasks, not coding-agent implementation obligations.
7. **Password-hash algorithm:** recommended `argon2-cffi` (Argon2id). Confirm, or choose bcrypt (72-byte limit caveat documented).
8. **Session lifetimes:** recommended access 60 min + refresh 7 d rotation. Confirm or adjust.
9. **Rate-limit numbers:** recommended 10/min/IP + 60/min/user on analyze, 5/min/IP on login. Confirm or adjust.
10. **Signup endpoint:** recommended none (seeded accounts only). A yes adds abuse surface + scope — strongly discouraged.

## 29. Three-Approach Comparisons

**A. Token model.**
- A1 — **chosen: opaque bearer tokens** (server-side `sessions` table, hashed, expiring, revocable). Revocation trivial, no crypto in client, matches migrationrun. Cost: one extra table + lookup per request.
- A2 — stateless JWT. No server state, but revocation needs denylists (reintroducing state) and secret rotation is riskier. Rejected.
- A3 — long-lived per-user API keys. Simplest, but coarse (no expiry/rotation story, leaks are catastrophic). Rejected for interactive use.

**B. ML shape.**
- B1 — **chosen: registry + bounded signal + synthetic `train.py` + published eval, default off.** Proves the slot end-to-end with honest, disclosed metrics; shippable even if cut to interface-only.
- B2 — interface-only, never train. Cheapest and fully honest, but leaves the registry untested dead code and the DoD's "validated" wording unmet. Fallback, not plan.
- B3 — real dataset training. No licensable data, no provenance path, no training infra in this environment. Rejected.

**C. Advisory provider.**
- C1 — **chosen: `StubProvider` (deterministic templates, offline, default) + optional generic-HTTP provider behind env.** Demo-reliable, fully testable incl. timeout/error injection, zero new deps.
- C2 — vendor SDK integration. Adds deps, keys, network dependence; violates venue checklist. Rejected.
- C3 — no advisory code at all. Cheapest, but migrationrun explicitly requires the layer; the stub is small and the invariant test needs a subject. Rejected.

**D. Rate limiting.**
- D1 — **chosen: in-memory sliding windows** (per-IP + per-user), injectable clock, single-worker compose. Zero deps, fully testable.
- D2 — `slowapi` library. Still in-memory by default; adds a dependency for no capability gain. Rejected.
- D3 — Redis. Correct for multi-instance, but new infrastructure for a demo; explicitly unnecessary. Rejected.

**E. Frontend hosting in compose.**
- E1 — **chosen: nginx static + `/api` reverse proxy.** One container, no CORS issues in demo (same origin), tiny config.
- E2 — `vite preview` server. Dev-grade, no proxy config story, wrong tool. Rejected.
- E3 — serve SPA from FastAPI `StaticFiles`. Couples frontend deploys to API releases; muddies the two-service story. Rejected.

**F. Password hashing.**
- F1 — **chosen: `argon2-cffi`** (Argon2id, modern, wheels). 
- F2 — `bcrypt`. Fine but 72-byte password caveat + older API. Reserve fallback.
- F3 — stdlib `hashlib.pbkdf2_hmac`. Zero deps but weaker defaults story and more hand-rolled code around a credential path. Rejected for the credential path specifically.

## 30. Scope Tripwires

Run after implementation; any hit blocks slice acceptance:

1. `rg -l "visual forensics|logo detect|reputation API|dns\.resolver|whois|fetch_url|urlopen|requests\.get" backend/app web/src` → empty.
2. `rg -l "\.pkl|joblib\.load\(.*sentinel|sklearn.*sentinel" backend tests` → empty (only `ml/` registry paths + synthetic artifacts allowed).
3. New-route audit: `api/routes/` contains exactly `analyze,audit,health,scans,stats,auth` (+`__init__`); frontend `Route` list identical to Slice 3.
4. New-page audit: `pages/` contains no new files beyond test files; no new nav items in `TopBar`.
5. Dependency audit: `requirements.txt` adds only `argon2-cffi`; new `requirements-ml.txt` holds sklearn/joblib; `package.json` adds nothing.
6. Migration audit: `alembic/versions` holds exactly `0001,0002,0003`; `downgrade -1` chain verified in tests.
7. UI-diff audit: `git diff --stat web/src` touches only `LoginPage,App,ResultPage,state/session,api/auth,components/AdvisoryNote` (+tests); token CSS untouched.
8. Claim audit: `rg -i "accuracy|precision|recall|f1|auc|state.of.the.art|SOTA" README.md web/src backend/ml/EVAL.md` → every hit traceable to `EVAL.md` numbers with the synthetic qualifier.
9. Reference audit: `sentinelpay-main/` at 164 files; no `.pkl` path in `vh-s02/` outside `ml/artifacts/README` (which documents quarantine).
10. Secret audit: `rg -i "password\s*=\s*['\"][^'\"]|api[_-]?key\s*=\s*['\"]|secret\s*=\s*['\"]" backend/app web/src` → empty (tests use env-provided fixtures).

## 31. Slice 4 Definition of Done

- [ ] Unified pipeline serves all four types; ML slot proven (or honestly absent) with disclosed backend; advisory optional/redacted/isolated.
- [ ] Auth + ownership enforced and tested; rate limits enforced and tested; CORS/secrets/hosts/headers/size/upload/audit hardening tested.
- [ ] Full suite green: Slice 3 tests unmodified + new tests (§19) + `ruff` + `tsc` + `vitest` + `vite build` (+ `docker build`s where docker exists).
- [ ] PG parity proven where PG available (migrations, goldens, chain, seen, old rows); SQLite default intact.
- [ ] Compose one-command start + seed + demo script pass (or environment-blocked record where docker is unavailable); `DEMO_SCRIPT.md` + README prepared (backup-video recording and venue hosting are manual final-demo tasks, not implementation gates).
- [ ] Manual verification (§20) recorded with output + screenshots.
- [ ] No Slice 5 artefacts (§30 clear); single migration `0003`; no new pages; no redesign.
- [ ] `sentinelpay-main/` unchanged; no upstream code/`.pkl`; open items closed or deferred in writing.
- [ ] Git tag `slice-4` (only if the repo is initialised for tagging).

---

## Summary

**What Slice 4 will add:** an honest, optional intelligence layer (synthetic-data ML slot with published eval + redacted advisory-only guidance that cannot move verdicts); real auth with user-scoped data (`users`/`sessions` + `0003`); server-side rate limiting; configuration hardening (production guards, CORS, hosts, headers, size caps, error hygiene, log redaction); Postgres-via-Compose with seed data; CI with tests/builds; `DEMO_SCRIPT.md` + README completion. Nothing else. (Backup-video recording and venue hosting are manual final-demo tasks.)

**What remains unchanged:** the deterministic pipeline, all four analyzers' scoring math, golden corpora, thresholds, contract shapes (additive only), audit-chain canonical form, all six routes/pages/navigation/tokens, gates, balance demo, existing migrations, and the `MODEL_BACKEND=none` safe default.

**Biggest risks:** (1) time overrun across six workstreams — mitigated by §18 order with pre-agreed cutbacks (ML→interface-only); (2) synthetic-ML overclaim — mitigated by EVAL.md + disclosure + default-off + claim sweep; (3) auth lockout at demo — mitigated by flag-off rehearsal path; (4) environment gaps (no docker/PG here) — mitigated by environment-dependent verification marks.

**Biggest expensive-to-reverse decisions:** opaque-token auth model (§27.1), nullable `user_id` (§27.2), frozen `FEATURES_V1` schema (§27.3), advisory contract + signals-only policy (§27.4), compose topology (§27.5), global-chain audit scope (§27.6).

**Recommended implementation order:** §18 increments 1→6 (hardening → limits → auth → ML → advisory → compose/demo), each gated on focused tests + full Slice 3 regression + tripwire check.

**Blocking open decisions:** §28 items 6 (venue hosting owner), 10 (signup — recommend no), and 4 (raw-text advisory — recommend no); all others proceed on stated defaults.
