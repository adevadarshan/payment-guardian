# Slice 2 Implementation Plan — Core SentinelPay Migration

**Status:** PLAN ONLY — nothing implemented. No source files modified.
**Plan date:** 2026-09-29
**Governing document:** `D:\New folder (3)\sentipay\migrationrun.md` §5 (Slice 2), §§1–3, 8–13.
**New project:** `D:\New folder (3)\sentipay\vh-s02\`
**Amendments applied during implementation (normative):**
- **A1 — magnitude asymptote.** The plan's §6.6 "near limit" row expected 75/HIGH at
  ₹199,000–200,000. Verified by running the exact upstream formula: at the maximum
  valid amount (200,000) the floor is `round(75/(1+e^-5)) = 74`. Amount alone therefore
  cannot reach HIGH by design; HIGH needs one more signal. Golden case corrected to
  `200000 / Utilities → 74 MEDIUM` with reason `payment.amount_magnitude`.
- **A2 — server-trusted hour.** Per implementation instruction, production scoring uses
  server time (`datetime.now(timezone.utc).hour`). The request `timestamp` is honoured
  only when `ALLOW_CLIENT_HOUR=true`, which is set in `tests/conftest.py` and defaults
  to false (`.env.example`). Client time can never move a production verdict.
- **A3 — golden payee ids.** `x@y` rejected by the UPI pattern (single-char labels);
  corrected to `xx@bank`. Vectors `bet@play`, `power@utility`, etc. already valid.
- **A4 — signals ordering.** `signals[]` (after `payment.base`) is emitted in the same
  contribution-descending order as `reasons[]`; asserted by test.

---

## 1. Objective

Port SentinelPay's real payment-analysis behaviour into the web app while preserving the SentinelPay UI structure: deterministic risk scoring with named signals, full persistence, API-backed history with server-side filters, a stats-backed dashboard with charts, server-chain audit with live verification, and the complete gated submission workflow. Fix the four audit blockers (validation wiring, category mapping, thresholds, dropped fields).

**Explicitly not this slice:** message/URL/QR analysis, seen detection, cross-type fusion, ML, LLM advisory, real auth, server rate limiting, Docker/CI, UI redesign, new pages.

---

## 2. Current Slice 1 State

Verified by reading the actual code in `vh-s02/` (not from the prior report).

### 2.1 What Slice 1 built and works

**Backend** (`vh-s02/backend/`):
- `app/main.py` — FastAPI app, CORS allowlist from env, stable 422 `validation_error` envelope, lifespan startup log. Routes mounted: `/api/health`, `/api/analyze`, `/api/scans`, `/api/scans/{id}`, `/api/categories`, `/api/audit`, `/api/audit/verify`.
- `app/config.py` — env settings (`DATABASE_URL`, `CORS_ORIGINS`, `MODEL_BACKEND=none`, `THRESHOLD_MEDIUM=35`, `THRESHOLD_HIGH=75`, `PIPELINE_VERSION=slice-1`). SQLite default; Postgres target.
- `app/categories.py` — 24-label registry `{key, type, risk_weight}`; exposed via `GET /api/categories`.
- `app/schemas/analyze.py` — full `AnalysisResult` contract (`scan_id`, `analysis_type`, `risk_score`, `risk_level`, `reasons[]`, `signals[]`, `evidence`, `seen`, `recommended_action`, `advisory`, `model`, `pipeline_version`, `created_at`) plus `AnalyzeRequest` (payment-only, amount/balance/category/payee validators) and `ScanSummary`.
- `app/api/routes/analyze.py` — **STUB**: validates, persists all 8 payment columns, appends one `SCAN_SUBMITTED` audit entry, returns `risk_score 0 / SAFE / pipeline.not_implemented`. **Must be replaced this slice.**
- `app/repositories/{scans,audit}.py` — plain functions; scans list is newest-first with limit only.
- `app/services/audit_service.py` — clean-room hash chain (canonical JSON, sorted keys, compact separators), append + full re-verify. Tested.
- `alembic/versions/0001_initial.py` — `scans` (all payment columns + `result_json`) and `audit_log`. Verified to apply.
- Tests: 8 passing (`test_analyze.py`, `test_persistence_audit.py`).

**Frontend** (`vh-s02/web/src/`):
- Six routed pages behind a demo-session guard: `Login`, `Transaction`, `Result/:id`, `Dashboard`, `History`, `Audit`; shared `TopBar`; token CSS; typed API client with `ApiError` union.
- `TransactionPage` — balance/receiver/amount/category/note form, categories from API, client gates (`lib/gates.ts`: 5/min rate limit, UPI regex, amount range, note sanitiser, probe patterns), chain dot read **once** on load, submit → `/result/:id`, loading/error states.
- `ResultPage` — static score number (`ScoreReadout`), level badge, recommended action, reasons list, transaction summary, browser-context echo, New Transaction / View Dashboard links.
- `DashboardPage` — tiles + fraud-rate + alerts + live feed **computed client-side** from `/api/scans`. No charts.
- `HistoryPage` — **client-side** level filter chips over one `/api/scans` fetch.
- `AuditPage` — server chain list, Verify button, JSON export, status display. No polling.
- `lib/{constants,format,gates,fingerprint}.ts`; `components/widgets.tsx` (7 widgets, no `RiskIndicator`).
- Tests: 4 passing Vitest; `tsc` clean; `vite build` succeeds.

### 2.2 Gaps Slice 2 must close (verified absent)

No `RiskIndicator`, no `ReasonList`/`SafeActionCard` components, no `recharts` dependency, no `GET /api/stats`, no `level`/`type` filters on `GET /api/scans`, no `payment_analyzer`, no `pipeline/` directory, no 5-second verify polling, no breach dialog, no Make-Payment flow, no payment echo in results, no timestamp input, stub reason still producible. `AuditLog` payload holds the score (there is **no** `risk_score` column — migrationrun §5.6 step 6's `UPDATE audit_log SET risk_score=1` is wrong for our schema; corrected in §13).

---

## 3. Reference Behavior Inspected

All paths relative to `sentinelpay-main/`. Used to understand behaviour only; nothing is copied.

| # | File | Behaviour established for Slice 2 |
|---|---|---|
| R1 | `sentinel_backend/model.py:39-40, 177-196` | Note keyword families: urgent `{urgent, blocked, suspend, otp, prize}` → strong uplift; info `{kyc, verify, claim, refund}` → weaker uplift. Sigmoid magnitude `1/(1+exp(-10*(amount/200000-0.5)))` scaled ×75 via `max()`. Drain `amount/(balance+1) > 0.90` → forced high. |
| R2 | `sentinel_backend/model.py:197-208, 214-219` | Merchant `risk_weight` 0.6–1.9 applied as a multiplier (with ×0.9 dampening when <1.0). Final clamp 0–100. Thresholds **HIGH ≥ 75, MEDIUM ≥ 35** — the only definition that shipped in code. |
| R3 | `sentinel_backend/model.py:74-102` | `MERCHANT_PROFILES` risk ordering: Gambling/Crypto/Cash-out highest; Peer/Remittance high; Travel/Electronics elevated; Grocery/Utilities/Insurance/Salary lowest. Informs the Slice 2 category table. |
| R4 | `sentinel_backend/model.py:223-253` | Dead code after `return` (older +60 heuristic, 70/30 thresholds). **Must not be ported.** |
| R5 | `sentinelpay_app/lib/utils/constants.dart:47-52, 59-88` | 24 category labels (verbatim source for our registry labels); demo creds; `RiskLevel` labels SAFE/SUSPICIOUS/HIGH RISK and the three canonical action strings: SAFE → "Transaction appears legitimate. Proceed normally." / MEDIUM → "Unusual patterns detected. Request additional verification." / HIGH → "Potential fraud detected. Block transaction & alert user." |
| R6 | `sentinelpay_app/lib/services/api_service.dart:138-172` | Mock scorer tiers: amount >10000/+40, >5000/+25, >2000/+15, >500/+5; high-risk cats Electronics/Travel +25; medium Entertainment/Clothing +12; night 0–5h +20; 22h+ +10; base 10. Informs Slice 2 calibration (mock is behaviour users saw in demos). |
| R7 | `sentinelpay_app/lib/security/security_service.dart:82-205` | Client gates: UPI regex, amount range ≤200000, note strip→length cap, 5/min sliding window, probe patterns (uniform stepping, sub-threshold clustering). UX-only pattern to preserve. |
| R8 | `sentinelpay_app/lib/screens/transaction_screen.dart` | 6-gate submit order; 5s `GET /audit/verify` poll with non-dismissible breach dialog → "view chain" action; chain dot in header; AppBar nav to dashboard/audit/history; rate-limit countdown; security warning banner. |
| R9 | `sentinelpay_app/lib/screens/risk_result_screen.dart:29, 127-180, 239-249` | Gauge + level pill; Make-Payment flow: warning confirm dialog for suspicious/high → deduct `currentBalance - amount` → broadcast new balance → success snackbar with amounts; chain dot + breach strip; back resets analysis. |
| R10 | `sentinelpay_app/lib/screens/dashboard_screen.dart:50-133, 248-357` | Section order: SUMMARY tiles (Total Transactions / Fraud Detected / Suspicious / Safe) → fraud-rate card (>20% flagged) → RISK DISTRIBUTION pie (3 sections, % labels, Safe/Suspicious/High-Risk legend, "No data" empty) → RISK SCORE HISTOGRAM (5 buckets 0-20…81-100, colour by bucket index) → ACTIVE ALERTS (high, take 3) → SUSPICIOUS ACTIVITY (take 2) → LIVE FEED (take 20). |
| R11 | `sentinelpay_app/lib/screens/transaction_history_screen.dart:52-176` | Chips All/Safe/Suspicious/High Risk (toggle), "N transactions" count, empty state, clear-history with confirm dialog. **Decision:** the Clear action is dropped in Slice 2 (see §9.7) — with DB-backed history there is no safe server-side equivalent and the audit log must stay append-only. |
| R12 | `sentinelpay_app/lib/screens/audit_log_screen.dart:128-199` | Chain Integrity card (status-coloured, entry counter), result box after verify, empty-state explainer, JSON export. Poll-every-second `setState` is **not** ported; replaced by sane refresh. |
| R13 | `DEVELOPER_GUIDE.md` §14 | Three demo scenarios (safe grocery ₹150 daytime / suspicious ₹3,500 Electronics evening / high-risk ₹12,000 Travel 2:30 AM) — the seed of the golden set. |

---

## 4. Architecture Changes

Slice 2 adds behaviour inside the Slice 1 skeleton. No new top-level directories except `backend/app/pipeline/` and `backend/app/analyzers/`. No new tables. No new pages. One new npm dependency (`recharts`, pie + bar only).

```
backend/app/
  pipeline/
    __init__.py
    rules.py            # deterministic payment scoring primitives (pure functions)
    thresholds.py       # classify(score) from config; single source
  analyzers/
    __init__.py
    payment_analyzer.py # validated payment -> (score, level, reasons, signals, evidence, action)
  api/routes/
    stats.py            # NEW: GET /api/stats
    analyze.py          # MODIFIED: stub replaced by analyzer call
    scans.py            # MODIFIED: + level/type filters
    audit.py            # unchanged (verify/list already correct)
    health.py           # unchanged
  config.py             # MODIFIED: PIPELINE_VERSION default "slice-2"

web/src/
  components/
    RiskIndicator.tsx   # NEW: static SVG gauge
    ReasonList.tsx      # NEW: ordered reasons
    SafeActionCard.tsx  # NEW: headline + steps
    widgets.tsx         # MODIFIED: remove ScoreReadout (replaced by RiskIndicator)
  pages/
    ResultPage.tsx      # MODIFIED: real verdict rendering + Make Payment
    DashboardPage.tsx   # MODIFIED: stats API + Recharts pie/histogram
    HistoryPage.tsx     # MODIFIED: server-side filter chips, drop Clear action
    TransactionPage.tsx # MODIFIED: 5s verify poll + breach dialog
    AuditPage.tsx       # MODIFIED: 10s list refresh, event labels
    LoginPage.tsx       # unchanged
  lib/
    api (analyze.ts)    # MODIFIED: fetchStats, scans(level, type)
```

---

## 5. Backend Implementation Plan

### 5.1 `app/pipeline/rules.py` (new) — pure scoring primitives, no I/O
- **Current:** does not exist.
- **Required:** deterministic functions with no randomness, no clock reads, no DB access:
  - `amount_tier(amount: float) -> tuple[int, str | None]` — additive tiers: `>=100000:+45`, `>=50000:+35`, `>=20000:+30`, `>=10000:+25`, `>=5000:+15`, `>=2000:+10`, `>=500:+4`, else `+0`. Returns (points, reason-code-or-None); tiers at `+0` emit no reason.
  - `category_points(label, registry) -> tuple[int, dict]` — flat table (see §6.3); returns points + profile for observation text.
  - `hour_points(hour: int | None) -> tuple[int, str | None]` — `0–4:+20`, `22–23:+10`, else `+0`; `None` (unparseable/missing timestamp) → `+0`, no reason.
  - `drain_points(amount, balance) -> tuple[float, bool]` — ratio + `is_ceiling` flag for `> 0.90`.
  - `magnitude_floor(amount) -> int` — `round(75 / (1 + exp(-10 * (amount/200000 - 0.5))))`.
  - `note_hits(note: str | None) -> tuple[str | None, list[str]]` — `"urgent"` or `"info"` or `None`, plus matched phrases. Word-boundary, case-insensitive match against the two upstream families (R1). If both families match, `"urgent"` wins (mirrors upstream if/elif).
  - `payee_unverified(payee_name: str | None) -> bool` — `True` when missing, blank, or case-insensitive `"unknown"`.
- **Approach:** plain module-level functions + module-level constant tables (`AMOUNT_TIERS`, `CATEGORY_POINTS`, `URGENT_WORDS`, `INFO_WORDS`). No classes, no config reads inside (thresholds live in `thresholds.py`).
- **Verify:** unit tests per function (boundary values included) + golden tests (§12).

### 5.2 `app/pipeline/thresholds.py` (new) — single threshold source
- **Current:** thresholds exist in config but nothing classifies; the stub hardcodes `"SAFE"`.
- **Required:** `classify(score: int) -> Literal["SAFE","MEDIUM","HIGH"]` reading `settings.THRESHOLD_MEDIUM` (35) / `settings.THRESHOLD_HIGH` (75): `score >= HIGH → HIGH`; `score >= MEDIUM → MEDIUM`; else `SAFE`. Boundary-inclusive at the lower edge (35 → MEDIUM, 75 → HIGH).
- **Verify:** `test_thresholds_are_server_owned` (§12).

### 5.3 `app/analyzers/payment_analyzer.py` (new) — validated payment → verdict parts
- **Current:** does not exist (route builds the stub inline).
- **Required:** `analyze_payment(payment: PaymentInput, timestamp: str | None) -> dict` returning `{risk_score, risk_level, reasons, signals, evidence, recommended_action}`:
  1. `score = 5` (base; emit as signal `payment.base`, not a reason).
  2. Add tier/category/hour/drain-elevated/note/payee points, appending one `Reason` + one `Signal` per firing rule (codes in §6.4). Drain `> 0.90`: `score = max(score, 85)` + ceiling reason (no additive points in that branch). Magnitude: `score = max(score, magnitude_floor)` + reason only when the floor binds.
  3. `score = clamp(round(score), 0, 100)`; `risk_level = classify(score)`.
  4. Safe action selected by level from the §6.5 table (headlines are the R5 canonical strings verbatim).
  5. `evidence = {extracted_urls: [], matched_phrases: <note hits>, qr_payload: None, decoded: False}`.
  6. Deterministic: same input → identical output (no clock, no random). Hour comes from the request `timestamp`, never `now()` (see §7.2).
- **Verify:** golden tests, determinism test, reasons invariant test.

### 5.4 `app/api/routes/analyze.py` (modify) — stub replaced
- **Current:** builds stub `AnalysisResult` inline (lines 29–~100).
- **Required:** parse optional `timestamp`, call `analyze_payment`, persist all payment columns (unchanged), store `result_json`, append `SCAN_SUBMITTED` audit entry with `{analysis_type, risk_score, risk_level, pipeline_version}` (unchanged shape), return the verdict with `pipeline_version` from settings (`slice-2`). Delete the stub block and its comment. Keep `GET /api/categories` untouched.
- **Verify:** `test_stub_removed` (no response may contain `pipeline.not_implemented`; every fixture scan re-fetched from DB matches), updated contract test.

### 5.5 `app/api/routes/scans.py` (modify) — server-side filters
- **Current:** `GET /api/scans?limit` only.
- **Required:** add `level: str | None` (validated against SAFE/MEDIUM/HIGH; anything else → 422 via the existing envelope) and `type: str | None` (payment only in Slice 2; other values → 422). Repository gains `list_scans(db, limit, level=None, analysis_type=None)`. Ordering unchanged (newest first).
- **Verify:** persistence/filter round-trip tests.

### 5.6 `app/api/routes/stats.py` (new) — dashboard totals
- **Current:** does not exist (dashboard derives client-side).
- **Required:** `GET /api/stats` → `{total, safe, medium, high, fraud_rate}` where `fraud_rate = round(high/total, 4)` (`0.0` when empty). Single aggregate query path; counts from the same `scans` table the history reads.
- **Verify:** `test_stats_aggregation`.

### 5.7 `app/config.py`, `.env.example` (modify)
- **Current:** `PIPELINE_VERSION = "slice-1"`.
- **Required:** default `"slice-2"`; `.env.example` updated to match. No other config changes (thresholds already present).

### 5.8 Unchanged backend files
`main.py`, `health.py`, `audit.py`, `categories.py` (values already correct), `db/*`, `repositories/audit.py`, `services/audit_service.py`, `schemas/analyze.py` except the §7 additions, `alembic/*` (no migration).

---

## 6. Payment Scoring Specification

Normative for the implementer. Any deviation must update the golden set in the same commit with a written reason.

### 6.1 Inputs
`amount, sender_balance, merchant_category (registry label), note | None, payee_id, payee_name | None, channel, timestamp | None` (ISO-8601; hour extracted server-side; unparseable → hour signal skipped, request still valid).

### 6.2 Computation order
```
score = 5                                                            # base, signal only
score += AMOUNT_TIERS(amount)                                        # §6.3
score += CATEGORY_POINTS[merchant_category]                          # §6.3
score += HOUR_POINTS(hour_of(timestamp))                             # §6.3, None-safe
ratio = amount / sender_balance
if ratio > 0.90: score = max(score, 85)            # ceiling, reason payment.balance_drain
elif ratio > 0.60: score += 15                     # reason payment.balance_drain_elevated
score = max(score, magnitude_floor(amount))        # reason payment.amount_magnitude iff binds
family, phrases = note_hits(note)
if family == "urgent": score += 50                 # reason payment.note.urgent
elif family == "info": score += 25                 # reason payment.note.credential
if payee_unverified(payee_name): score += 5        # reason payment.payee_unverified
score = clamp(round(score), 0, 100)
level = classify(score)                            # 35 / 75, server-owned
```

### 6.3 Tables (exact values)

**AMOUNT_TIERS** (points): `amount >= 100000 → 45`; `>= 50000 → 35`; `>= 20000 → 30`; `>= 10000 → 25`; `>= 5000 → 15`; `>= 2000 → 10`; `>= 500 → 4`; else `0`. Reason code `payment.amount_tier`, impact `medium` if points ≥ 25 else `low`, observation names the crossed tier (e.g. `"Amount Rs.12,000 crosses the Rs.10,000 tier"`).

**CATEGORY_POINTS**: Crypto `25`, Gambling `25`, Cash Advance `20`, ATM / Cash Withdrawal `20`, Travel `20`, Electronics `20`, Peer Transfer `12`, Remittance `12`, Wallet / Top-up `12`, Entertainment `10`, Clothing `10`, Retail / Shopping `10`, Fuel `10`, Food & Dining `6`, Investment `6`, Loan Repayment `6`, Groceries/Utilities/Insurance/Healthcare/Education/Subscription/Salary / Payroll `0`, Other `8`. Reason code `payment.category.<profile-key-lowercase>` (e.g. `payment.category.travel`), impact `high` if ≥ 20, `medium` if ≥ 10, `low` otherwise; zero-point categories emit no reason. Observation names the label (e.g. `"Category Travel carries elevated risk"`).

**HOUR_POINTS**: hour `0–4 → 20`, `22–23 → 10`, else `0`. Reason code `payment.unusual_hour`, impact `medium`, observation includes the clock time (e.g. `"Submitted at 02:30 — unusual hour"`). Impact `low` for the 22–23 band.

**Note families** (word-boundary, case-insensitive; matched phrases recorded verbatim-lowercased into `evidence.matched_phrases`):
- urgent: `{urgent, blocked, suspend, otp, prize}` → `+50`, code `payment.note.urgent`, impact `high`, observation names the matched word(s).
- info: `{kyc, verify, claim, refund}` → `+25`, code `payment.note.credential`, impact `medium`. Suppressed when urgent fires.

**Payee**: unverified → `+5`, code `payment.payee_unverified`, impact `low`, observation `"Payee name not provided — cannot confirm recipient"`.

**Ceilings/floors**: drain ceiling reason `payment.balance_drain` impact `high` (`"Uses 95% of the sender balance"`); elevated-drain reason `payment.balance_drain_elevated` impact `medium`; magnitude reason `payment.amount_magnitude` impact `medium` (`"Amount Rs.199,000 approaches the Rs.200,000 limit"`).

### 6.4 Reason/observation style rules
- One reason per firing rule, ordered by contribution descending (ties: ceilings first, then amount, category, note, hour, payee).
- Observations state facts with numbers; never hedge ("possibly", "might").
- `signals[]` contains the base plus one entry per firing rule: `{name: <code>, source: "rule", value: <raw: amount/ratio/hour/weight or null for note>, weight: null, contribution: <points>}` in the same order as reasons.

### 6.5 Safe-action table (headlines verbatim from R5)
- SAFE — headline `"Transaction appears legitimate. Proceed normally."`, steps: `["If anything about this request feels off, confirm the payee through a channel you already trust."]`
- MEDIUM — headline `"Unusual patterns detected. Request additional verification."`, steps: `["Pause before paying.", "Confirm the payee name and UPI ID with the recipient directly — not through any link or number in this request.", "Check that the amount matches what you agreed."]`
- HIGH — headline `"Potential fraud detected. Block transaction & alert user."`, steps: `["Do not pay.", "Never share an OTP, PIN, or CVV — no legitimate payment asks for one.", "If you already paid, contact your bank immediately."]`

### 6.6 Calibration proof (golden expectations the implementer must satisfy)
| Case | Computation | Score → Level |
|---|---|---|
| Safe grocery ₹150 / Groceries / bal 5000 / 14:00 / "groceries" / known payee | 5+0+0+0 | 5 SAFE, no reasons |
| Suspicious ₹3,500 / Electronics / bal 20000 / daytime | 5+10+20 | 35 MEDIUM (boundary) |
| High-risk demo ₹12,000 / Travel / bal 50000 / 02:30 / Unknown | 5+25+20+20+5 | 75 HIGH (boundary) |
| Drain 95%: ₹9,500 / Groceries / bal 10000 | 5+10+0 → ceiling 85 | 85 HIGH, drain reason |
| Urgent note: ₹12,000 / Peer Transfer / "urgent verify kyc" | 5+25+12+50 | 92 HIGH, note reason (info suppressed) |
| Near-limit ₹199,000 / Utilities / bal 500000 | 5+45+0 → magnitude 75 | 75 HIGH, magnitude reason |
| Info-only note ₹800 / Utilities / "refund claim" | 5+4+0+25 | 34 SAFE |
| Night benign ₹300 / Groceries / 03:00 | 5+0+0+20 | 25 SAFE with hour reason |
| Crypto ₹5,000 / bal 50000 | 5+15+25 | 45 MEDIUM |
| Gambling drain ₹60,000 / bal 65000 | 5+35+25 → ceiling 85 | 85 HIGH |
Full golden list (~13 cases) lives in `tests/test_golden_payment.py` with expected band + expected reason codes.

---

## 7. API Contract Changes

All changes are additive except the stub replacement. `AnalysisResult` shape is unchanged.

1. **`AnalyzeRequest` gains optional `timestamp: str | None`** (ISO-8601). Used only to derive hour-of-day. Absent/unparseable → hour signal skipped; request remains valid. Every other field and validator unchanged.
2. **`AnalysisResult` gains `payment_summary`** — `{amount: float, payee_id: str, payee_name: str | None, merchant_category: str, channel: str} | None` (default `None`). Populated by the analyze route so the Result page renders a summary without a second fetch. Required in Slice 2 responses (tests assert presence for payment analyses).
3. **`GET /api/scans` gains `level` and `type` query params.** `level ∈ {SAFE, MEDIUM, HIGH}` (else 422 via the existing envelope); `type` accepts `payment` (other values → 422 until Slice 3). Combines with `limit`.
4. **New `GET /api/stats`** → `{total: int, safe: int, medium: int, high: int, fraud_rate: float}`. Key names are new (upstream used `medium_risk`/`high_risk`; ours are shorter and consistent with `risk_level` values minus prefix — document the choice).
5. **Pipeline version** responses report `"slice-2"`.
6. **No changes** to `/api/health`, `/api/categories`, `/api/audit`, `/api/audit/verify`, `/api/scans/{id}`, or the 422 envelope.

---

## 8. Database Changes

**None. No migration in Slice 2.**

- Every Slice 2 field already exists in `0001_initial`: all 8 payment columns, `result_json` (holds reasons/signals/evidence/action), audit columns.
- Filters and stats are read queries against `scans`; hour-of-day is derived per request, never stored.
- Compatibility impact: zero — `0001_initial` applies unchanged; existing Slice 1 rows remain valid (their `result_json` keeps `pipeline_version: "slice-1"`, which History/Dashboard must tolerate: unknown/old versions render normally, never crash).
- If the implementer believes a column is needed, stop and re-read this section: the answer is `result_json` or a derived query. A schema change requires a written justification and becomes `0002_*`, but the plan expects this not to happen.

---

## 9. Frontend Implementation Plan

For each item: file → current → required → approach → verification.

### 9.1 `components/RiskIndicator.tsx` (new) — the gauge
- Current: absent; `ScoreReadout` shows a static number.
- Required: static SVG arc gauge, props `{score: number (0–100), size?: number}`, colour from level (reuse `levelClass` tokens), numeric score centred. Same visual role as `RiskIndicator(score, size: 180)` in R9; no animation library.
- Approach: SVG background arc + foreground arc (stroke-dasharray by fraction) + centred score text. Pure presentational component with its own unit test (renders score text; colour class matches level bands).
- Verify: unit test + Result page screenshot.

### 9.2 `components/ReasonList.tsx` (new) + `components/SafeActionCard.tsx` (new)
- Current: reasons rendered inline as `AlertBanner`s in `ResultPage`; action headline inline.
- Required: `ReasonList({reasons})` renders ordered reasons (title + observation, impact-tinted marker); `SafeActionCard({action})` renders headline + steps list. No new visual language — same cards, same tokens.
- Approach: extract from `ResultPage` into components; keep copy exactly as returned by the API.
- Verify: Result renders stubbed reasons/action (existing pattern extended).

### 9.3 `pages/ResultPage.tsx` (modify) — real verdict
- Current: static score readout, action, reasons-as-banners, summary, browser echo, nav links.
- Required: `RiskIndicator` + level badge; `ReasonList`; `SafeActionCard`; summary card extended with `payment_summary` (amount formatted INR, payee id/name, category, channel); browser-context echo retained; **Make Payment flow** (R9): button → confirm dialog for MEDIUM/HIGH (custom modal in existing card style; SAFE pays immediately) → deduct from a `localStorage` session balance (`vhs02-balance`, seeded from the analysed `sender_balance` on first result view) → success confirmation showing paid amount + new balance → links update Transaction balance field on return (via the stored balance, read on Transaction mount).
- Approach: fetch by `:id` (unchanged); payment echo comes from the response (no second fetch). Modal is a minimal overlay `div`, no library.
- Verify: frontend tests — renders score/reasons/action/summary; Make Payment on HIGH shows confirm then deducts and shows confirmation; SAFE skips confirm; balance persists across reload.

### 9.4 `pages/DashboardPage.tsx` (modify) — stats API + charts
- Current: tiles/fraud/ alerts/feed derived client-side; no charts.
- Required: `GET /api/stats` drives tiles + fraud-rate card (flag style when rate > 20%, per R10); **pie** (Recharts `PieChart`, 3 sections safe/suspicious/high with % labels + legend + "No data" empty state, same order); **histogram** (Recharts `BarChart`, 5 buckets `0–20…81–100`, bar colour by bucket index: 0–1 safe, 2–3 suspicious, 4 danger); ACTIVE ALERTS (high, take 3), SUSPICIOUS ACTIVITY (take 2), LIVE FEED (take 20 from `/api/scans`). Same section order as R10.
- Approach: add `recharts` dependency (sole new dep; pie + bar only). Two data fetches (stats + scans list) with shared loading/error states.
- Verify: renders tiles/charts/alerts from mocked API; empty-state test.

### 9.5 `pages/HistoryPage.tsx` (modify) — server-side filters
- Current: one fetch, client-side chips.
- Required: chips `All/Safe/Suspicious/High Risk` (same labels, toggle behaviour per R11) call `GET /api/scans?level=`; "N transactions" count label; empty state; **remove the Clear action** — with DB-backed history there is no safe equivalent and the audit log must stay append-only (documented UI change, not a redesign).
- Approach: `api/scans.ts` gains `(limit, level?)` params; refetch on chip change with loading state.
- Verify: chip click issues the right query; count updates; no Clear button rendered.

### 9.6 `pages/TransactionPage.tsx` (modify) — live chain verification
- Current: chain dot from a single verify call on mount; gates; submit flow.
- Required: 5-second `setInterval` poll of `POST /api/audit/verify` (cleanup on unmount; skip overlapping requests); red dot + non-dismissible breach dialog naming `broken_at_id`/`reason` with a "View audit log" action (R8); green dot when valid; silent on network error (no false alarms, per R8). API base already configured — confirm no placeholder URLs remain (grep gate in tests/CI-less check).
- Approach: small `useChainPoll` hook in the page file (shared later if Result needs it — Result keeps its mount-time check only in Slice 2 to bound scope).
- Verify: mocked invalid verify → dialog appears with entry id; valid → dot green; unmount clears timer (assert via test teardown, no warnings).

### 9.7 `pages/AuditPage.tsx` (modify) — event labels + sane refresh
- Current: list + Verify + export.
- Required: render `SCAN_SUBMITTED` entries (icon/label mapping function for event types; unknown types render generically, never crash); keep Verify + export; replace any per-second refresh with 10-second list refresh + manual Verify (R12 parity without the `setState` storm).
- Verify: renders the new event type; verify valid/broken states (extend existing pattern).

### 9.8 `pages/LoginPage.tsx` — unchanged.

### 9.9 `lib/api` changes
- `analyze.ts`: add `fetchStats()`, extend `fetchScans(limit, level?, type?)`, add `Stats` type to `types.ts`. No other client changes.

### 9.10 Dependency change
- Add `recharts` (exact minor pin in `package.json`). No animation, icon, or component libraries.

---

## 10. Client Gate Plan

`lib/gates.ts` already implements the five gates; Slice 2 keeps them **exactly as UX pre-checks** and adds nothing security-relevant client-side.

| Gate | Client (exists) | Server parity (Slice 2, enforced) | Parity test |
|---|---|---|---|
| UPI format | `validateUpi` regex | `payee_id` pattern validator (same regex, already in schema) | same valid/invalid vectors both sides |
| Amount range | `validateAmount` (>0, ≤200000) | `amount` Field(gt=0, le=200000) (already in schema) | boundary vectors 0/1/200000/200001 |
| Amount ≤ balance | form-level check | model validator (already in schema) | 6000/5000 rejected both sides |
| Note length/sanitisation | `sanitiseNote` (strip markup/controls, 280) | `note` validator: max 280, control-char strip (already in schema) | markup/control vectors |
| Rate limit 5/min | `checkRateLimit` + countdown | **none in Slice 2** (server limiting is Slice 4). Document that rapid submits are UX-limited only. | n/a (explicitly deferred) |
| Probe patterns | `checkProbePattern` warning banner | **none** (advisory UX only; server scores each transaction independently) | n/a (explicitly client-only) |
| Category whitelist | dropdown from API | registry validator (already in schema) | unknown label rejected by server; dropdown prevents it client-side |

**Rule:** any input the client blocks must also be rejected by the server (`test_client_gate_parity`); anything the server accepts but the client blocks is a UX bug to fix, not a security property.

---

## 11. Audit Chain Integration

- **Write path (unchanged from Slice 1):** analyze route appends `SCAN_SUBMITTED` with `{analysis_type, risk_score, risk_level, pipeline_version}`. No new event types in Slice 2.
- **Read/verify (unchanged endpoints):** `GET /api/audit`, `POST /api/audit/verify` already exist and are tested. Slice 2 adds frontend consumption (poll + page) only.
- **Frontend consumption:** Transaction 5s poll + breach dialog (§9.6); Audit page labels + refresh (§9.7).
- **Tamper demonstration correction:** our schema stores the score inside `payload` JSON, so the manual step is `UPDATE audit_log SET payload = <modified JSON> WHERE id = <n>` (migrationrun §5.6 step 6 references a `risk_score` column that does not exist — this plan supersedes that line).
- **Invariant:** the audit chain remains the single chain; no local/frontend chain is introduced (the upstream Dart chain stays dead).

---

## 12. Test Plan

### Backend (`backend/tests/`, SQLite-backed as in Slice 1)
1. `test_golden_payment.py` — ~13 cases from §6.6, each asserting band **and** expected reason codes (subset match: all listed codes present; extra `low`-impact reasons allowed only if the test documents why).
2. `test_thresholds_are_server_owned` — `classify()` at 34/35/74/75; config override respected (monkeypatch settings); an HTTP case near a boundary classifies per server config.
3. `test_category_mapping` — all 24 labels resolve to their own profile (no `OTHER` fallback path exists; assert the registry lookup used by validation and scoring is the same object).
4. `test_persistence_roundtrip` (extend Slice 1) — submit → `GET /api/scans/{id}` identical fields **including** `payment_summary`; `level`/`type` filters return exact subsets.
5. `test_stats_aggregation` — seed known levels → totals + `fraud_rate` exact.
6. `test_audit_chain_tamper` (extend) — through the endpoint; assert `broken_at_id`; restore; valid again.
7. `test_client_gate_parity` — vectors from §10 rejected with 422 `validation_error`.
8. `test_stub_removed` — scan all analyze responses in the suite: no `pipeline.not_implemented`, all `pipeline_version == "slice-2"`.
9. `test_determinism` — same payload twice → identical `risk_score/reasons/signals/evidence/recommended_action` (excluding `scan_id`/`created_at`).
10. `test_reasons_invariant` — every MEDIUM/HIGH response in the suite has ≥1 reason.
11. Keep all Slice 1 tests green (update the stub contract test into the real contract test).

### Frontend (`web/src`, Vitest + TestingLibrary)
1. Result renders score gauge, level, reasons, action, summary from a stubbed Slice 2 response.
2. Make Payment: HIGH shows confirm dialog → confirm deducts + shows new balance; cancel aborts; SAFE skips confirm; balance persists across reload (localStorage).
3. History chips call `/api/scans?level=` with the right param; no Clear button.
4. Dashboard renders tiles + pie + histogram + alerts from mocked stats/scans; empty state with no data.
5. Audit renders `SCAN_SUBMITTED` entries; verify valid/broken states.
6. Transaction breach dialog appears on mocked invalid verify; timer cleaned on unmount.
7. `tsc --noEmit` clean; `vite build` succeeds.

---

## 13. Manual Verification Plan

Record command output + screenshots for each. SQLite stands in for Postgres (documented Slice 1 deviation); Postgres remains the deployment target.

1. Migrate fresh DB → submit the three `DEVELOPER_GUIDE.md` §14 demos → SAFE (`groceries ₹150`), MEDIUM (`Electronics ₹3,500`), HIGH (`Travel ₹12,000` 02:30) with sensible reasons.
2. Drain case: ₹9,500 of ₹10,000 → HIGH with the drain reason naming the ratio.
3. Note case: note `"urgent verify kyc"` → HIGH with the matched phrase shown; note `"refund claim"` on a small utilities payment → SAFE (info uplift alone must not condemn).
4. `/history`: each chip returns the right subset; restart backend → entries persist.
5. `/dashboard`: tiles, fraud-rate, pie %, histogram buckets, alerts all match the history list.
6. Tamper: `UPDATE audit_log SET payload='<modified JSON>' WHERE id=<n>` → Transaction dot red + breach dialog naming the entry; Audit Verify shows the break; restore row → green.
7. Restart backend + fresh browser profile → login → history intact; demo balance flow works.
8. Full suites green (`pytest -q`, `vitest run`, `tsc`, `vite build`); screenshots of all six pages.

---

## 14. Files to Create

**Backend:** `app/pipeline/__init__.py`, `app/pipeline/rules.py`, `app/pipeline/thresholds.py`, `app/analyzers/__init__.py`, `app/analyzers/payment_analyzer.py`, `app/api/routes/stats.py`, `tests/test_golden_payment.py`, `tests/test_scoring_units.py` (rules + thresholds + parity + determinism + stub-removed + invariant may live here or split — one file minimum, names as listed in §12).

**Frontend:** `components/RiskIndicator.tsx`, `components/ReasonList.tsx`, `components/SafeActionCard.tsx`, `components/BreachDialog.tsx` (small, Transaction-scoped modal), `components/ConfirmDialog.tsx` (reused by Make Payment; generic, no styling beyond tokens), frontend test additions (`ResultPage.test.tsx`, `DashboardPage.test.tsx`, `AuditPage.test.tsx`, extend existing two).

**Config/deps:** `recharts` in `web/package.json` (+ lockfile via `npm install`).

---

## 15. Files to Modify

| File | Current | Change |
|---|---|---|
| `backend/app/api/routes/analyze.py` | stub verdict inline | call `analyze_payment`; populate `payment_summary`; version `slice-2`; delete stub |
| `backend/app/api/routes/scans.py` | limit only | `+ level/type` params + validation |
| `backend/app/repositories/scans.py` | limit only | filter support |
| `backend/app/schemas/analyze.py` | no timestamp/echo | `+ timestamp?`, `+ payment_summary` |
| `backend/app/config.py` + `.env.example` | `PIPELINE_VERSION=slice-1` | `"slice-2"` |
| `backend/tests/test_analyze.py` | stub contract test | real contract test (stub assertions removed) |
| `backend/tests/test_persistence_audit.py` | passing | extend with filters/stats coverage (or new files — either, no duplication) |
| `web/src/components/widgets.tsx` | `ScoreReadout` | remove (replaced by `RiskIndicator`) |
| `web/src/pages/ResultPage.tsx` | static readout | §9.3 |
| `web/src/pages/DashboardPage.tsx` | client-side stats | §9.4 |
| `web/src/pages/HistoryPage.tsx` | client filters + (no clear btn in S1? verify) | §9.5; ensure no Clear action |
| `web/src/pages/TransactionPage.tsx` | one-shot verify | §9.6 poll + dialog |
| `web/src/pages/AuditPage.tsx` | list/verify/export | §9.7 labels + refresh |
| `web/src/api/analyze.ts` + `types.ts` | basic calls | stats, filtered scans, `Stats`/`payment_summary` types |
| `web/package.json` | no charts | `+ recharts` |
| `vh-s02/README.md` | Slice 1 runbook | note Slice 2 behaviour + Make-Payment/balance semantics |

**Do not touch:** `sentinelpay-main/` (anything), `alembic/*`, `db/*`, `audit_service.py`, `categories.py` values, `main.py`, `health.py`, `LoginPage.tsx`, token CSS values, `gates.ts` logic.

---

## 16. Scope Boundaries

**In:** everything in §§5–11. **Out (explicitly deferred, must not leak in):**
- Any second `analysis_type` accepted by the validator (still rejects non-`payment`).
- `app/pipeline/{normalize,signals,fuse,explain}.py`, `run.py` — Slice 3 names; do not create stubs "for later".
- Any `message/url/qr` analyzer, `qr_seen`, upload handling, `EvidencePanel`/`SeenStatusBadge`/`ScanTypeSelector` components.
- Any `ml/` directory, artifact, dependency, or score contribution.
- Any advisory/LLM code, prompt, key, or dependency.
- Real auth (login stays a `localStorage` demo flag), sessions, tokens, password hashing, `users` table.
- Server-side rate limiting (no middleware, no counters).
- `DELETE` endpoints, history clearing, data export beyond audit JSON.
- New pages, renamed routes, new nav items, new design tokens, animation/icon/chart libraries beyond Recharts pie+bar.
- Docker/CI.

**Leak tripwires** (if any appears in review, the slice is out of scope): a second analyzer file, an `ml` import, an `Authorization` header, a migration file, a new route path, a new page component.

---

## 17. Risks and Mitigations

| # | Risk | Mitigation |
|---|---|---|
| 1 | Calibration disputes (is 35/75 right? are tiers principled?) | Numbers are locked by the golden set, not by authority; any change updates tests + §6.6 table in the same commit. The scheme ports upstream's documented tiers/families/thresholds, so it is a migration, not an invention. |
| 2 | Boundary inclusivity confusion (35 MEDIUM vs 34 SAFE) | `classify` unit-tested at all four edges; golden cases sit on both boundaries deliberately (34 SAFE, 35 MEDIUM, 75 HIGH). |
| 3 | Client timestamp trust (hour signal from user input) | Documented: hour is advisory-grade input; impact capped at +20; server never trusts it for auth/rate decisions (none exist yet). Unparseable → skipped, request still valid. |
| 4 | `payee_name "Unknown"` heuristic misfires | Impact is only +5 with a `low` reason; never decisive alone (max without it still classifies the same in all golden cases — assert this in a test). |
| 5 | Recharts bundle weight/complexity | Pie + bar only; no other chart types; if it fights the build, fallback is SVG hand-rolled (same shapes, same data) — decide within the slice, don't add a second library. |
| 6 | Histogram bucket edges (score 20 → bucket 0 per `floor(20/20)=1`?) | Port upstream exactly: `idx = floor(score/20)` clamped 0–4 (so 20 lands in bucket 1, matching `riskScore` int math in R10). Tested. |
| 7 | Result page needs payment data the contract lacks | Solved by `payment_summary` (§7.2), not by a second fetch or a schema change. |
| 8 | Make-Payment balance semantics drift | Specified exactly in §9.3 (`vhs02-balance`, seeded from analysed `sender_balance`, Transaction reads on mount); no server balance exists in Slice 2 by design. |
| 9 | Scope leak into Slice 3/4 | §16 tripwires enforced at review; the validator still rejects non-payment inputs as a mechanical guard. |
| 10 | Reference-code transcription (clean-room breach) | Behaviour reimplemented from the tables above; reviewers check that no upstream file was opened during implementation beyond this plan's citations. |

---

## 18. Rollback Strategy

- Branch `slice/2-core`; Slice 1 tag is the restore point (`git checkout slice-1` or `git revert <range>`).
- Scoring is isolated in `app/pipeline/rules.py` + `app/analyzers/payment_analyzer.py`; a bad heuristic reverts without touching plumbing, persistence, or audit.
- No migration ships in Slice 2, so the database needs no rollback; Slice 1 rows remain readable (old `pipeline_version` values render, never crash — assert in a test).
- Frontend: component additions are additive; page edits revert cleanly. `recharts` removal = delete dep + two chart components (dashboard falls back to Slice 1 tiles-only only as an emergency measure, not a supported state).
- Worst case: delete `vh-s02/` fresh state is recoverable from the Slice 1 tag; `sentinelpay-main/` is never at risk.

---

## 19. Slice 2 Definition of Done

- [ ] `POST /api/analyze` scores real payment verdicts per §6; no stub reason producible anywhere.
- [ ] All four audit blockers fixed and tested: validation wired (single model, route-imported), categories single-sourced (24/24 resolve, no silent fallback), thresholds single-sourced server-owned (35/75), every accepted field persisted and round-trippable.
- [ ] `GET /api/scans` filters by level/type; `GET /api/stats` matches the table; audit verify detects tampering at the exact entry.
- [ ] Six pages recognisably SentinelPay with: working gauge, reasons, safe actions, Make-Payment deduction, pie + histogram, server-filtered history (no Clear action), labelled audit with verify/export, 5s poll + breach dialog, configured API base only.
- [ ] Golden set green; determinism, parity, invariant, and stub-removed tests green; frontend suite + `tsc` + `vite build` green.
- [ ] Manual verification (§13) recorded with output + six screenshots.
- [ ] No Slice 3/4 artefact present (§16 tripwires clear); no schema change; no new pages; no redesign.
- [ ] `sentinelpay-main/` unchanged; no upstream code or `.pkl` in the tree; README updated.
- [ ] Git tag `slice-2` (only if the repo is initialised for tagging; otherwise the branch head + this plan's evidence serve as the restore point).
