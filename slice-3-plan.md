# Slice 3 Implementation Plan — VH-S02 Detection Capabilities

**Status:** PLAN ONLY — nothing implemented. No source files modified.
**Plan date:** 2026-09-29
**Governing document:** `D:\New folder (3)\sentipay\migrationrun.md` §6 (Slice 3), §§1–3, 8–13.
**Prior plan + amendments:** `D:\New folder (3)\sentipay\vh-s02\slice-2-plan.md` (including A1–A4).
**New project:** `D:\New folder (3)\sentipay\vh-s02\`
**Reference (read-only):** `D:\New folder (3)\sentipay\sentinelpay-main\`
**Restore point:** Slice 2 (31 backend + 15 frontend tests green; contract `pipeline_version: "slice-2"`).

## 1. Objective

Add the VH-S02 detection capabilities into the existing migrated SentinelPay application — not as a separate app: message scam analysis, URL/link analysis, QR image upload with payload classification and previously-seen detection, richer payment context, deterministic cross-signal fusion, ordered explanations with evidence, and type-aware safe actions. Generalize `POST /api/analyze` to four input types while preserving Slice 2 payment behaviour under behavioral/contract identity (defined in §3.1): same risk_score, risk_level, ordered reasons, ordered signals, evidence, recommended_action, and validation behaviour for all Slice 2 golden cases. Extend the six existing screens with the minimum additive UI (one input-type selector, three result components, type chips).

**Explicitly not this slice:** ML registry/models, LLM advisory, real auth, server rate limiting, Docker/CI, hardening, UI redesign, new pages.

## 2. Current Slice 2 State

Verified by reading the actual code (not from reports).

### 2.1 Backend (`vh-s02/backend/`)
- `app/schemas/analyze.py` — `AnalysisResult` (scan_id, analysis_type, risk_score, risk_level, reasons[], signals[], evidence{extracted_urls, matched_phrases, qr_payload, decoded}, seen{status, first_seen_at, times_seen}, recommended_action{headline, steps}, advisory{always disabled}, model{backend none}, pipeline_version, created_at, payment_summary{amount, payee_id, payee_name, merchant_category, channel, sender_balance}); `AnalyzeRequest` (payment-only validator, optional advisory `timestamp`); `PaymentInput` (amount/balance/category/payee validators, note sanitised); `ScanSummary(label, …)`.
- `app/analyzers/payment_analyzer.py` — `analyze_payment(payment, *, hour)` → score/reasons/signals/evidence/action. Additive: base 5, amount tiers, category table, hour (+20/+10), drain ceiling 85 / elevated +15, sigmoid magnitude floor, urgent +50 / info +25 (urgent wins), payee-unverified +5; clamp; `classify()` 35/75 from config. Reasons/signals ordered contribution-desc. Hour comes from server time in production (`ALLOW_CLIENT_HOUR` test hatch only).
- `app/pipeline/{rules,thresholds}.py` — pure functions; no I/O, clock, or randomness.
- Routes: `POST /api/analyze` (payment only), `GET /api/categories` (24), `GET /api/scans` (limit/level/type=payment), `GET /api/scans/{id}`, `GET /api/stats` ({total,safe,medium,high,fraud_rate}), `GET /api/audit`, `POST /api/audit/verify`, `GET /api/health`. Stable 422 envelope.
- `app/db/models.py` — `scans` (8 payment_* columns, result_json, analysis_type/risk_level indexes), `audit_log` (hash chain). Migration `0001_initial` only.
- `app/services/audit_service.py` — append + full re-verify (frozen canonical form).
- Tests: 31 passing (`test_golden_payment` 10 cases, `test_scoring_units`, `test_analyze`, `test_persistence_audit`).

### 2.2 Frontend (`vh-s02/web/src/`)
- Routes (unchanged structure): `/login`, `/transaction`, `/result/:id`, `/dashboard`, `/history`, `/audit` behind a demo-session guard; `TopBar`; token CSS (values frozen).
- `TransactionPage` — payment form, gates (`lib/gates.ts`), 5s verify poll + `BreachDialog`, balance seeded from `lib/balance.ts`.
- `ResultPage` — `RiskIndicator`, `ReasonList`, `SafeActionCard`, payment summary, Make-Payment demo flow (`vhs02-balance`).
- `DashboardPage` — stats API, Recharts pie (3 sections) + 5-bucket histogram, alerts (high×3, medium×2), feed (×20).
- `HistoryPage` — server `level=` chips with toggle-to-All, count label, no Clear action.
- `AuditPage` — server chain, labels incl. `SCAN_SUBMITTED`, Verify, JSON export, 10s refresh.
- `api/analyze.ts` — `analyzePayment`, `fetchScans(limit, level?, type?)`, `fetchStats`, `fetchScan`, `fetchCategories`, `fetchAudit`, `verifyChain`; typed `ApiError`.
- Tests: 15 passing; `tsc` clean; `vite build` succeeds. Deps: react, react-router-dom, recharts (only chart lib).

### 2.3 Housekeeping noted during inspection
- Stray scratch DBs exist at `backend/vhs02.db` and `backend/legacy_probe.db` (gitignored via `*.db`, but must be deleted before the Slice 3 branch is cut so no stale rows leak into manual verification).
- No `ml/`, `llm/`, `auth/`, `users`, rate limiter, Dockerfile/CI exist — nothing to remove.

## 3. Slice 2 Behaviour That Must Not Regress

These are release gates for Slice 3; each has an existing test that must stay green unmodified (except the two named extensions):

### 3.1 Payment identity definition (normative)

"Preserving Slice 2 payment behaviour" means **behavioral/contract identity**, not
byte equality of stored artefacts: for every Slice 2 golden case, a payment-only
request through the Slice 3 pipeline must produce the same `risk_score`,
`risk_level`, ordered `reasons`, ordered `signals`, `evidence`,
`recommended_action`, and the same validation behaviour (accept/reject + 422 shape).
`scan_id`, `created_at`, and `pipeline_version` are expected to differ.
Architectural guarantee: a payment-only request traverses `fuse()` with a single
analyzer and the fusion of one signal set equals the analyzer output (asserted by
`test_payment_path_unchanged`, §20).

1. **Payment scoring identical (per §3.1).** All 10 golden cases in `tests/test_golden_payment.py` satisfy the identity above.
2. **Thresholds 35/75 server-owned**, boundary-inclusive (`test_thresholds_are_server_owned`).
3. **All 24 categories resolve** through the single registry; no silent fallback (`test_category_mapping`, extended only with the type-driven assertions in §20).
4. **Validation envelope stable** — 422 shape, parity vectors, unknown-category/balance/payee rejections.
5. **Persistence round-trip** of all 8 payment columns + `payment_summary`; Slice-1-shaped rows still read (200, `payment_summary: null`).
6. **Stats/audit endpoints** unchanged in shape; chain tamper still detected at the exact id.
7. **Frontend Slice 2 tests** (15) unchanged and green; Make-Payment semantics untouched.
8. **`ALLOW_CLIENT_HOUR=false` default** in production config; hour still server-trusted for payment.

## 4. VH-S02 Requirements Being Added

From migrationrun §6: input normalization; signal registry; deterministic cross-type fusion; explanation/evidence generation; safe-action generation; message analyzer (urgency, credential/KYC/OTP, incentives, pressure, threats, gift/crypto, deadlines, imperative+credential, impersonation, caps/punctuation/leetspeak/homoglyph); URL analyzer (IP host, deep subdomains, brand-in-subdomain, hyphens, punycode, shorteners, `@`, embedded credentials, non-HTTPS, ports, long/encoded query, redirect params, path keywords, exfil params, small risky-host list; no DNS/WHOIS/fetch); QR analyzer (upload caps, magic bytes, pixel caps, client preview decode + server-authoritative decode, payload classes upi_uri/url/text/contact/crypto/unknown, UPI field extraction pa/pn/am/cu/tr/tn/mc/rpayee, payload routing into URL/message/payment analyzers, QR-specific rules); `qr_seen` with previously_seen/new/unable_to_verify/not_applicable and the NEW≠SAFE rule; payment context enrichment; generalized discriminated `POST /api/analyze`; additive UI (selector, evidence, seen badge, type chips, multi-type dashboard/audit).

## 5. Architecture Changes

Slice 3 adds one pipeline layer and three analyzers inside the Slice 2 skeleton. No new top-level pages, no new services beyond `qr_seen_service.py`, no `ml/`/`llm/`/`auth/`.

```
backend/app/
  pipeline/
    normalize.py      # NEW: text/URL/payload normalisation (pure)
    signals.py        # NEW: Signal type + registry (pure data structures)
    fuse.py           # NEW: deterministic weighted-sum fusion + clamp + classify
    explain.py        # NEW: reasons ordering + evidence assembly + safe-action select
    run.py            # NEW: single orchestration entry analyze_request(req, ctx)
    rules.py, thresholds.py   # UNCHANGED (payment primitives stay put)
  analyzers/
    base.py           # NEW: Analyzer protocol (matches/analyze), ~20 lines
    payment_analyzer.py       # MODIFIED: emits Signal list; scoring math UNCHANGED
    message_analyzer.py       # NEW
    url_analyzer.py           # NEW
    qr_analyzer.py            # NEW (decode + classify + route + QR rules)
  services/
    qr_seen_service.py        # NEW: lookup + record by payload_hash
  repositories/
    qr_seen.py                # NEW: get/record
  schemas/analyze.py          # MODIFIED: MessageInput/UrlInput/QrInput, generalized
                              #   AnalyzeRequest, evidence += parsed_qr/payload_class
  api/routes/
    analyze.py                # MODIFIED: dispatch through run.py; persist per-type inputs
    scans.py                  # MODIFIED: type filter accepts 4 values; per-type labels
    stats.py                  # UNCHANGED (counts span types automatically)
    audit.py                  # UNCHANGED endpoints; new event types flow through
  db/models.py                # MODIFIED: + QrSeen model (0002)
  alembic/versions/0002_qr_seen.py  # NEW: sole migration this slice

web/src/
  components/
    ScanTypeSelector.tsx      # NEW: Payment/Message/Link/QR segmented control
    EvidencePanel.tsx         # NEW: urls/phrases/decoded payload/parsed UPI fields
    SeenStatusBadge.tsx       # NEW: previously_seen/new/unable_to_verify rendering
  pages/
    TransactionPage.tsx       # MODIFIED: selector + per-mode inputs + submit union
    ResultPage.tsx            # MODIFIED: + EvidencePanel + SeenStatusBadge
    HistoryPage.tsx           # MODIFIED: + type chips
    DashboardPage.tsx         # MODIFIED: + BY TYPE row (client-derived)
    AuditPage.tsx             # MODIFIED: + QR_SEEN labels (label-map extension)
  lib/
    qr.ts                     # NEW: client pre-checks (size/MIME) + jsqr preview decode
    api (analyze.ts, types.ts)# MODIFIED: union payloads, Stats unchanged
  package.json                # + jsqr only (preview decode; server is authoritative)
```

Data flow (the smallest connected path — no disconnected analyzers):
```
TransactionPage --(mode + input)--> POST /api/analyze
  --> validate (discriminated union) --> normalize --> run.py
  --> matching analyzer(s) --> Signal[] --> fuse (weighted sum, clamp, classify)
  --> explain (reasons + evidence + safe action) --> persist scans + audit
  --> qr_seen lookup/record (qr only) --> AnalysisResult
  --> ResultPage (gauge + reasons + evidence + seen badge + action)
      History (type+level filters) / Dashboard (stats + by-type row) / Audit (events)
```

### Implementation sequence (normative)

Do NOT implement Slice 3 in one pass. Build in small verified increments, in this order, running the focused tests for each increment **plus the complete existing Slice 2 regression suite** before continuing:

1. normalization + signals registry (+ `test_normalization.py`, registry unit tests)
2. generalized contract — schemas + discriminated validator + 422 matrix (`test_discriminated_union`); analyzers not yet wired (non-payment types return 422-unimplemented? No — validator accepts the shapes; route dispatches payment only until step 5 lands; message/url/qr requests return a 422 `not_implemented` error code until their analyzers land)
3. message analyzer (+ golden + benign corpora)
4. URL analyzer (+ golden + benign corpora, no-network test, `risky_hosts.json`)
5. fusion + explanation + `run.py` + payment refactor to `Signal`s (+ identity, determinism, ordering tests; Slice 2 goldens must pass here)
6. QR classification + UPI extraction + routing (payload-string path only; no decoding yet)
7. QR server decoding + upload hardening (+ limits, authority, fixture tests)
8. QR seen detection + `0002_qr_seen` (+ seen/NEW≠SAFE tests, `QR_SEEN` audit test)
9. frontend — selector, per-mode submits, evidence/seen components, type chips, by-type row, labels (+ Vitest per §20)
10. final integration — §21 manual verification, tripwire sweep (§Scope Tripwires), README, tag readiness

Each increment ends with: focused tests green, full Slice 2 suite green, no new tripwire hits.

## 6. Input Normalization Plan

- **Path:** `backend/app/pipeline/normalize.py` (new) — pure functions, no I/O.
- **Current behaviour:** payment fields validated by Pydantic; note control-chars stripped in schema; no shared normalizer.
- **Required behaviour:**
  - `normalize_text(s, *, cap=4000)`: strip → NFKC → casefold → leetspeak map (`0→o,1→l,3→e,4→a,5→s,7→t,@→a,$→s,+→t`) → homoglyph map (explicit minimal table: Cyrillic а/с/е/о/р/х, Greek ο/ρ/ν plus ~10 curations with a comment citing confusable intent) → collapse whitespace → truncate to cap. Returns `(normalized, was_truncated)`.
  - `extract_urls(text)`: regex for `https?://` and `www.` tokens (no fetching, no validation beyond syntactic split); returns de-duplicated list, capped at 10.
  - `normalize_url(raw, *, cap=2048)`: strip → length cap → `urllib.parse.urlsplit`; lowercase scheme/host; drop default ports; return parts dict. Raises `ValueError` on unparseable input (route maps to 422).
  - `normalize_qr_payload(raw: str)`: NFKC → strip → length cap 8192. `qr_payload_hash(norm)`: for `upi://` payloads, sort query parameters by key before hashing; otherwise hash the normalized string as-is. SHA-256 hex.
- **Implementation approach:** one module, table-driven maps at top, each function independently unit-testable. Leet/homoglyph maps are explicit literals (reviewable, no external data files).
- **Verification method:** `test_normalization.py` — truncation flags, map applications (`"0TP"`→`"otp"`, homoglyph confusables), URL extraction counts/caps, hash stability across param reorder/whitespace/case variants.

## 7. Signal Registry

- **Path:** `backend/app/pipeline/signals.py` (new).
- **Current behaviour:** payment signals are ad-hoc dicts built inside `payment_analyzer.py`.
- **Required behaviour:** a single `Signal` dataclass `{name, source: Literal["rule"], value: float|None, contribution: float, observation: str}` plus `WEIGHTS: dict[str, float]` — the one fusion weight table (default 1.0; entries only where an analyzer needs scaling). `payment_analyzer` is refactored to emit `Signal` objects with identical contributions (no scoring change; mechanical refactor covered by the unchanged golden file).
- **Implementation approach:** dataclass + helpers; weights applied only inside `fuse.py`, never in analyzers.
- **Verification method:** `test_payment_path_unchanged` compares full verdicts; unit test that every emitted signal name exists in the registry.

## 8. Message Analyzer

- **Path:** `backend/app/analyzers/message_analyzer.py` (new, implements `base.Analyzer`).
- **Current behaviour:** none (payment note keywords stay untouched inside the payment analyzer).
- **Required behaviour:** `matches(t) = t == "message"`. `analyze(msg, ctx)` returns signals:
  - Keyword families (word-boundary on normalized text; matched phrases → evidence): urgency `{urgent, immediately, "act now", expires, "last chance", hurry}` +25; credential `{otp, pin, cvv, password, kyc, verify, verification, "account number"}` +25; incentive `{lottery, prize, won, winner, reward, cashback, refund, claim, gift}` +15; pressure `{pay now, immediately, today only, blocked, suspended, frozen, deactivated, "account will be"}` +25 (note: overlapping words across families are allowed to fire independently here — unlike the payment-note elif — because cross-family compounding is itself a scam marker; cap total keyword contribution at +60); threat `{police, court, legal, arrest, "fraud department", rbi}` +15; gift/crypto `{gift card, "google play", itunes, crypto, usdt, bitcoin, "wallet address"}` +15.
  - Structural: deadline phrase (`\d+\s*(minutes?|hours?)` near urgency words) +15; imperative+credential co-occurrence (imperative verb list × credential family in same message) +15; impersonation (brand list `rbi, sbi, hdfc, icici, axis, kotak, paytm, phonepe, gpay, "google pay", upi, npci` appearing with a credential/request verb, sender context unknown) +20; caps ratio (>40% alpha caps and length>20) +8; punctuation runs (`!!!`, `???`, 3+ mixed) +5.
  - Each signal: code `message.<family|structure>`, observation quoting the matched fragment (truncated 80 chars), impact by points (≥20 high, ≥10 medium, else low).
  - Benign guard: messages under 3 tokens with no hits emit nothing (no reasons, score stays base).
- **Implementation approach:** table-driven families + small regexes; normalization via §6 first; matched phrases collected into evidence.
- **Verification method:** golden scam corpus (each family), benign corpus (bank SMS, bill receipt — must stay SAFE; legitimate OTP-delivery notices that merely state an OTP without requesting disclosure must stay SAFE, while urgency+disclosure-request combinations must fire), per-family unit tests, homoglyph/leet cases, no-false-positive budget asserted on the benign set.

## 9. URL Analyzer

- **Path:** `backend/app/analyzers/url_analyzer.py` (new). Stdlib `urllib.parse` only.
- **Current behaviour:** none.
- **Required behaviour:** `matches(t) = t == "url"` (also invoked internally for URL payloads/extracted links). Signals on normalized parts:
  - IP-literal host +25 (`url.ip_host`); punycode `xn--` +20; `@` in authority +15; embedded credentials (`user:pass@`) +20; non-HTTPS scheme +10; explicit non-default port +8; subdomain depth ≥3 +10 (`url.deep_subdomain`); brand-in-subdomain (registrable domain = last two labels; brand list from §8 matched in any other label) +25; hyphen count ≥3 in host +8; shortener host (committed list: `bit.ly, tinyurl.com, t.co, goo.gl, ow.ly, is.gd, cutt.ly, rb.gy, s.id, tiny.cc`) +15; path keywords (`login, verify, otp, payment, kyc, refund, wallet, apk, update, secure`) +10 each capped at +20; exfil params (`email, phone, otp, pin, cc, pan, upi, account, password`) +15; redirect params (`url, next, redirect, return, continue, dest`) +10; query length >200 or percent-encoded blobs +8; risky-host exact match (committed `risky_hosts.json`, ≤50 entries — curated demo/test heuristic data with a provenance comment, NOT live threat intelligence; a match is an indicator that contributes to the score, never proof of maliciousness) +30.
  - Observations quote the observed substring (e.g. `Host is an IP literal: 185.22.1.4`).
- **Implementation approach:** pure function of the parts dict; risky-host list is a committed JSON file framed as curated demo/test heuristic data (source comment per entry group; a match is an indicator, never proof of maliciousness); shortener/brand/path tables are module literals.
- **Verification method:** golden URL corpus (each signal), benign corpus (bank/official domains stay SAFE), shortener-without-fetch test (analyzer imports no network modules — asserted by an import scan test), punycode/IP/redirect unit tests.
- **Explicitly not built:** DNS, WHOIS, live fetching, reputation APIs, redirect following.

## 10. QR Analyzer

- **Path:** `backend/app/analyzers/qr_analyzer.py` (new).
- **Current behaviour:** none; `Evidence.qr_payload/decoded` exist but are always null/false.
- **Required behaviour:**
  - Intake (route-level, before decode): accept **either** `image_base64` **or** `payload` (client-decoded string), never both required; both-missing → 422. `image_base64` cap: 5 MB decoded bytes; magic-byte sniff (PNG `89 50 4E 47`, JPEG `FF D8 FF`, WEBP `RIFF....WEBP`, GIF `GIF8`) — client MIME ignored; decoded pixel cap 12 MP (above → 413); decode via OpenCV `QRCodeDetector().detectAndDecode` in a resource-bounded call; any decode failure on a well-formed image → `decoded=false`, path to `unable_to_verify` (never 500).
  - **Decoder availability rule (normative):** OpenCV missing/unimportable at startup is a configuration failure — the app must fail loudly at startup (import + smoke-decode check in the QR analyzer module load path), never silently degrade. A malformed or unreadable QR image at request time is a routine `unable_to_verify` runtime outcome. The two must never be conflated: missing library ≠ undecodable image.
  - Classification (ordered predicates, first match wins): starts with `upi://` (case-insensitive) → `upi_uri`; matches `^https?://` → `url`; matches contact patterns (`BEGIN:VCARD`, `tel:`, `mailto:`, `SMSTO:`/`sms:`) → `contact`; matches crypto patterns (`bitcoin:`, `ethereum:`, `^bc1[qp]`, `^0x[0-9a-fA-F]{40}$`) → `crypto`; empty/binary-after-strip → `unknown`; else `text` (2 KB retained preview; hash always over full normalized payload).
  - UPI extraction: parse `upi://pay?...` query into `{pa, pn, am, cu, tr, tn, mc, rpayee}` (missing → None; `am` float-or-None; values truncated 256 chars). No network, no VPA verification.
  - Routing: `url` → `url_analyzer` on the payload; `text` → `message_analyzer` on the payload; `contact` → +10 `qr.contact_payload` (low); `crypto` → +20 `qr.crypto_payload` (medium); `upi_uri` → UPI-mapped signals (amount tier + magnitude on `am` if present; malformed `pa` → +15 `qr.upi_bad_payee`; normalized `pn` tokens vs `pa` local-part tokens disjoint → +15 `qr.merchant_mismatch`; `am` vs attached payment-context amount conflict → +20 `qr.amount_conflict`).
  - QR-specific: `qr.unverifiable` informational reason on decode failure (forces `unable_to_verify`); evidence records `qr_decode: client|server|both|failed`.
- **Implementation approach:** decode helper isolated (`_decode_image`) so tests stub bytes→payload without OpenCV; classification as ordered predicate list; UPI parse with `urllib.parse.parse_qsl`.
- **Verification method:** fixture QR PNGs generated at test time via `qrcode[pil]` (test-only dev dep): valid UPI QR, URL QR, text QR, corrupted bytes, non-QR image, oversized payload, >5 MB upload, wrong magic bytes, pixel-bomb dimensions; classification unit tests; UPI extraction incl. missing keys; routing tests (`url.*`/`message.*` reasons from QR payloads); decode-authority test (server re-decodes when image present; client `payload` ignored in that case).

## 11. QR Seen Detection

- **Path:** `backend/app/services/qr_seen_service.py` + `backend/app/repositories/qr_seen.py` (new); table `qr_seen` via migration `0002_qr_seen` (see §16).
- **Current behaviour:** `SeenInfo.status` always `not_applicable`; no storage.
- **Required behaviour:**
  - On every QR analysis with a decodable payload: `h = qr_payload_hash(normalized)` → lookup. Miss → insert `{payload_hash: h, payload_class, normalized_preview (first 120 chars; full payload retained in `result_json.evidence.qr_payload` only when `STORE_QR_PAYLOADS=true`, default true for Slice 3, redaction review in Slice 4)}` → status `new` + informational reason `qr.seen_new` ("First time seen — a new code is not a verified-safe code"). Hit → bump `times_seen`, `last_seen_at` → status `previously_seen` + informational reason with first-seen date and count. Decode failure → `unable_to_verify` (no row). Non-QR types → `not_applicable` (unchanged).
  - **Logging redaction rule (normative):** full QR payloads must never enter application logs at any level, regardless of `STORE_QR_PAYLOADS`. Audit records carry only the hash prefix + class (§18). `STORE_QR_PAYLOADS` governs `result_json.evidence.qr_payload` retention only.
  - **NEW ≠ SAFE, enforced three ways:** (1) fixed badge copy (§17); (2) `qr.seen_new` informational reason on every `new` verdict; (3) `test_new_qr_is_not_safe` asserts a low-score `new` QR still carries the reason and no "safe/legitimate/verified" wording is ever tied to seen-status.
- **Implementation approach:** `lookup(db, h)` / `record(db, ...)`; route calls after fusion input known, before response build; audit event `QR_SEEN` appended only on first sighting (no chain spam on rescans).
- **Verification method:** first scan → `new` + row; rescan → `previously_seen`, `times_seen=2`, same `first_seen_at`; variant payloads → same hash; corrupt image → `unable_to_verify`, no row; copy test for NEW≠SAFE wording.

## 12. Cross-Type Fusion

- **Path:** `backend/app/pipeline/fuse.py` (new).
- **Current behaviour:** payment analyzer sums internally; no shared fusion.
- **Required behaviour:** `fuse(signals, *, weights=WEIGHTS) -> int` = `clamp(round(sum(w(name) * contribution)))`. `run.py` concatenates analyzer outputs. **Payment-path identity (per §3.1):** `fuse(payment_signals)` reproduces the Slice-2 score for every golden case (payment analyzer keeps its internal sum as reference; fuse must reproduce it — tested, not assumed). Thresholds via existing `classify()`. Base handling: the 5-point `payment.base` is emitted only by the payment analyzer; message/url/qr analyses have no base — fusion is a pure sum, so payment-only requests satisfy the §3.1 identity.
- **Implementation approach:** single function + `WEIGHTS` table (all 1.0 in Slice 3; the table exists so retuning has one place). No max() overlays, no per-type branches.
- **Verification method:** `test_fusion_identity` (all Slice 2 goldens through `run.py` unchanged), `test_fusion_determinism`, `test_fusion_ordering`.

## 13. Explanation and Evidence

- **Path:** `backend/app/pipeline/explain.py` (new).
- **Current behaviour:** payment analyzer builds reasons/evidence inline; `Evidence` has empty url/phrase slots for non-payment.
- **Required behaviour:** `explain(signals, *, analysis_type) -> (reasons, evidence, action)`:
  - Reasons: one per firing signal (skip zero-contribution), ordered contribution-desc with the Slice 2 tie-break (ceilings → amount → category → note → hour → payee, then message/url/qr codes alphabetically within equal contribution). Non-SAFE verdicts always carry ≥1 reason.
  - Evidence assembly: `extracted_urls` (message text / URL input / QR payload, capped 10, 256 chars each), `matched_phrases` (union across analyzers, de-duplicated, capped 20), `qr_payload` (per `STORE_QR_PAYLOADS`), `decoded` unchanged, **`parsed_qr: dict = {}`** (new), **`payload_class: str | None = None`** (new).
  - Contract change is additive: two new optional `Evidence` fields with defaults — old rows validate.
- **Implementation approach:** pure functions over the signal list; analyzers own wording, `explain` only orders and bundles.
- **Verification method:** composition test (message-with-URL yields both families + populated `extracted_urls`); evidence-cap tests; old-row tolerance extended to the new fields.

## 14. Safe Action

- **Path:** generated inside `explain.py` (`select_action(level, signals, analysis_type)`); no new module.
- **Current behaviour:** Slice 2 level table (SAFE/MEDIUM/HIGH headlines verbatim from SentinelPay constants).
- **Required behaviour:** base action by level (unchanged headlines/steps), plus type-specific appended steps:
  - message: MEDIUM/HIGH += `"Do not reply, call back, or click anything in the message. Contact the organisation through a number you already trust."`
  - url: MEDIUM/HIGH += `"Do not enter passwords, OTPs, or payment details on this page. If you already did, change that password and alert your bank."`
  - qr `new`: any level += `"This code is new to us — that is not a safety signal. Anyone can generate a QR. Verify the recipient out-of-band before paying."`
  - qr `previously_seen`: informational line with first-seen date/count is a reason, not an action change; actions stay level-based (repeated sightings are common for legitimate merchant codes).
  - qr `unable_to_verify`: floor action at MEDIUM regardless of score (`"We could not read this code. Do not scan it again elsewhere — verify the recipient another way."`).
- **Implementation approach:** level table (moved verbatim from `payment_analyzer.py` into `explain.py`; payment analyzer keeps no action logic after refactor) + per-type step appenders.
- **Verification method:** golden tests assert exact headlines per level and presence of type steps; `unable_to_verify` floor test.

## 15. Generalized API Contract

- **Path:** `backend/app/schemas/analyze.py` (modify); `backend/app/api/routes/analyze.py` (modify dispatch).
- **Current behaviour:** `AnalyzeRequest` accepts payment only; anything else → 422.
- **Required behaviour:**
  ```python
  class MessageInput(BaseModel):
      text: str = Field(..., min_length=1, max_length=4000)
      context: Literal["sms","whatsapp","email","unknown"] = "unknown"
  class UrlInput(BaseModel):
      url: str = Field(..., min_length=1, max_length=2048)
  class QrInput(BaseModel):
      image_base64: str | None = None   # raw upload, server-decoded (authority)
      payload: str | None = None        # client-decoded string (preview/convenience)
      # exactly one of the two must be present (model validator); image wins when both given
  class PaymentContext(BaseModel):      # optional enrichment for message/url/qr
      amount: float | None = Field(default=None, gt=0, le=200000)
      sender_balance: float | None = Field(default=None, gt=0)
      payee_name: str | None = Field(default=None, max_length=256)
  class AnalyzeRequest(BaseModel):
      analysis_type: Literal["payment","message","url","qr"]
      payment: PaymentInput | None = None
      message: MessageInput | None = None
      url: UrlInput | None = None
      qr: QrInput | None = None
      payment_context: PaymentContext | None = None   # NOT with analysis_type="payment"
      timestamp: str | None = None                    # unchanged advisory semantics
      # model validator: exactly the block matching analysis_type must be present;
      # payment_context forbidden when analysis_type == "payment" (422 otherwise).
  ```
- **Backward compatibility (exact):** payment requests validate and score exactly as Slice 2 (same fields, same rules, same response shape + the two new `Evidence` defaults). `GET /api/scans`, `GET /api/scans/{id}`, `GET /api/stats`, audit endpoints: unchanged shapes. `ScanSummary.label` per type: payment `"Rs.{amount:g} to {payee_id}"` (unchanged); message first 40 chars of text; url host + truncated path; qr `"QR {payload_class}: {preview-40}"` / `"QR undecodable"`.
- **Persistence per type:** `scans` row always written with `analysis_type`, score, level, version, `result_json`. Type inputs stored: message → new nullable columns? No — decision: type-specific inputs live in `result_json.input_echo` (new optional dict in stored JSON only, not a response field... simpler: reuse columns where they exist is wrong). Specified: add NO input columns; store `{input_text, input_url, input_qr_payload_hash, payment_context}` inside `result_json` under key `input_echo`. Keeps 0002 to the single `qr_seen` table (§16).
- **Implementation approach:** discriminated validator first (TDD: write the 422 matrix before analyzers); route dispatches to `run.py`.
- **Verification method:** `test_discriminated_union` (all valid combos 200-path shape; all mismatched/missing combos 422 with envelope); payment regression suite untouched.

## 16. Database Changes

**One migration: `0002_qr_seen`. Nothing else.**

- **Why:** previously-seen lookup needs a keyed, cross-scan store with its own lifecycle (first/last seen, counts). `result_json` cannot serve indexed hash lookups; `scans` must not gain QR-specific columns (keeps the table type-neutral).
- **Migration number/file:** `alembic/versions/0002_qr_seen.py` (`down_revision = "0001_initial"`).
- **Exact table:**
  ```
  qr_seen
    payload_hash      CHAR(64) PRIMARY KEY
    payload_class     VARCHAR(16) NOT NULL   # upi_uri|url|text|contact|crypto|unknown
    normalized_preview VARCHAR(280) NOT NULL # first 120 chars of normalized payload
    first_seen_at     TIMESTAMPTZ NOT NULL (server_default now())
    last_seen_at      TIMESTAMPTZ NOT NULL (server_default now())
    times_seen        INTEGER NOT NULL DEFAULT 1 (CHECK >= 1)
    first_scan_id     VARCHAR(36) NULL REFERENCES scans(id) ON DELETE SET NULL
  ```
- **Indexes/constraints:** PK covers the lookup path; no secondary index needed in Slice 3.
- **Compatibility impact:** purely additive; `0001` untouched; existing rows unaffected; downgrade drops the table (seen-data loss on downgrade is acceptable and documented — seen data is regenerable from rescan... precisely: regenerable only if payloads are rescanned; state this).
- **SQLite behaviour:** all types map cleanly (`CHAR`→TEXT-affinity, `TIMESTAMPTZ`→DATETIME, FK enforced only if pragma on — lookups don't depend on FK enforcement; tests assert service behaviour, not FK cascades).
- **PostgreSQL behaviour:** identical DDL via Alembic; PK + FK + CHECK all enforced.
- **Rollback:** `alembic downgrade -1` or leave the empty table in place (harmless; code paths degrade to `new` when the table is absent? No — code requires the table; rollback = code revert + optional downgrade. State both options.)
- **ORM:** `QrSeen` model added to `app/db/models.py` alongside existing models (no edits to `Scan`/`AuditLog`).

## 17. Frontend Migration

No new pages. No route changes. Token values frozen. Single new runtime dep (`jsqr`, client preview decode only).

- **Path:** `TransactionPage.tsx` (modify) — add `ScanTypeSelector` (segmented Payment/Message/Link/QR control) reusing the existing form card:
  - Payment mode: existing fields unchanged (default mode; preserves current behaviour).
  - Message mode: textarea (4000 max, counter) + context select (SMS/WhatsApp/Email/Unknown) + optional collapsible "payment context" (amount, balance, payee name — sent as `payment_context`).
  - Link mode: URL input + same optional payment-context collapsible.
  - QR mode: file drop/picker (accept `image/*`, client pre-check ≤5 MB, preview thumbnail via object URL) **or** pasted-payload textarea (for testing/undecodable-camera cases); `jsqr` decodes the preview client-side for instant feedback text ("Decoded: upi://…", never a verdict); submit sends `image_base64` (preferred when a file is present) or `payload`.
  - Submit builds the discriminated payload; per-mode client validation (non-empty, URL syntactic check, file present-or-pasted); navigates to `/result/:id` unchanged.
- **Path:** `ResultPage.tsx` (modify) — add `EvidencePanel` (extracted URLs list, matched phrases chips, decoded-payload block with `payload_class`, parsed UPI field table when present) under the existing gauge/reasons; add `SeenStatusBadge` (QR only): `previously_seen` (neutral: "Seen before — first {date}, {n} times"), `new` (muted + mandatory note "A new code is not a safe code"), `unable_to_verify` (warning: "Could not read this code"). Make-Payment flow unchanged (payment summaries only; non-payment results hide it).
- **Path:** `HistoryPage.tsx` (modify) — add type chips row (All/Payment/Message/Link/QR) calling `fetchScans(limit, level?, type?)`; level chips unchanged.
- **Path:** `DashboardPage.tsx` (modify) — add compact "BY TYPE" row (counts per type derived client-side from the scans list; no stats change); all existing sections unchanged.
- **Path:** `AuditPage.tsx` (modify) — extend `eventLabel` map with `QR_SEEN` ("QR first seen"); unknown types still render generically.
- **Path:** `lib/qr.ts` (new) — `checkImageFile(file): string|null` (size/type), `decodePreview(dataUrl): string|null` via `jsqr` (best-effort, exceptions swallowed → null), `fileToBase64(file, 5MB cap)`.
- **Path:** `api/analyze.ts`, `api/types.ts` (modify) — union request/response types (`MessageInput/UrlInput/QrInput/PaymentContext`, `parsed_qr`, `payload_class`, `SeenInfo` unchanged shape).
- **Implementation approach:** mode state is a single `mode` union in `TransactionPage`; per-mode sub-components in the same file (small) to avoid prop-drilling; everything downstream (submit/result/history) already type-agnostic except the new components.
- **Verification method:** per-mode submit tests (payload shapes), evidence/seen rendering tests, type-chip query tests, dashboard by-type test, audit-label test (§20).

## 18. History/Dashboard/Audit Integration

- **Path:** backend `scans.py` route + `repositories/scans.py` (modify); frontend `History/Dashboard/Audit` pages (modify).
- **Current behaviour:** `type` filter accepts `payment` only; stats span one type trivially; audit shows `SCAN_SUBMITTED`.
- **Required behaviour:**
  - `GET /api/scans?type=` accepts `payment|message|url|qr` (else 422); combines with `level` and `limit`; ordering unchanged.
  - `GET /api/stats` unchanged in shape (counts now span types automatically — same table, same query). No `by_type` server field in Slice 3 (dashboard derives it client-side; server breakdown deferred to Slice 4 analytics if needed).
  - Audit: `SCAN_SUBMITTED` payload gains `analysis_type` value varying by scan (already present as a field — no format change); new `QR_SEEN` event `{payload_hash_prefix (first 12 chars only — never the full hash in the chain payload... decision: audit payload carries `payload_class` + hash prefix for correlation without leaking reversible payload data), first_scan_id}` on first sightings.
  - Frontend History type chips; Dashboard BY TYPE row; Audit label map.
- **Implementation approach:** widen the existing `Literal` (one-line change) + label formats (§15); no repository restructuring.
- **Verification method:** type-filter round-trip per type; stats spanning mixed types; `QR_SEEN` appears once per hash (rescan creates no new audit entry — asserted).

## 19. Security and Upload Boundaries

All enforced server-side; client checks are UX hints only.

| Threat | Control (normative) |
|---|---|
| Oversized upload | Reject `image_base64` decoding to >5 MB with 413 + envelope (`too_large`); client blocks earlier with the same message. |
| Wrong MIME / polyglot | Ignore client MIME entirely; sniff magic bytes; allow PNG/JPEG/WEBP/GIF only → else 422 (`unsupported_media`). |
| Malformed / hostile images | Decode inside bounded call (pixel cap 12 MP checked from header/dimensions before full decode where possible); any exception → `unable_to_verify`, never 500. |
| Pixel-bomb | Cap decoded dimensions (e.g. width×height ≤ 12 MP); above → 413. |
| Huge payload | `normalize_qr_payload` cap 8192 chars; retained preview 2 KB; hash over full normalized payload. |
| Malicious UPI payload | Parse-only handling: length caps, strict field truncation, unknown params tolerated+recorded; never executed, rendered, or followed. |
| URL in payload | Static analysis only — no fetch, no DNS, no redirect following (asserted by import-scan test + no-network test). |
| Oversized text/URL inputs | `message.text` 4000, `url.url` 2048 enforced by Pydantic (422). |
| Payload privacy | Full payload in `result_json` only behind `STORE_QR_PAYLOADS` (default true S3); application logs never carry payloads at any level; audit carries hash prefix + class only. |
| ReDoS | All regexes are linear-time constructions (character classes, bounded quantifiers); no nested quantifiers; review checklist item. |
| Dependency weight | `opencv-python-headless` (~50 MB) + `qrcode[pil]` (tests only) + `jsqr` (client). No zbar system dependency (Windows installer risk rejected). |

## 20. Test Plan

Backend (`backend/tests/`, existing SQLite harness; new `tests/fixtures/` only if binary fixtures prove necessary — prefer runtime generation):

1. `test_normalization.py` — caps/flags, leet + homoglyph maps, URL extraction, hash stability.
2. `test_golden_message.py` — scam corpus: urgency, credential/KYC/OTP, incentive, pressure, threat, gift/crypto, deadline, imperative+credential, impersonation, caps/punct (each with expected band + reason codes).
3. `test_benign_messages.py` — bank SMS, bill receipt, personal chat: all SAFE (no-false-positive budget). Legitimate OTP *delivery* messages (e.g. "Your OTP is 482913. Do not share it.") contain OTP-related words but are informational rather than requesting disclosure: they must remain SAFE. Scam messages combining urgency with credential-disclosure requests (e.g. "verify OTP now", "share your OTP") must still trigger the relevant signals — the discriminator is request-for-disclosure + pressure context, not the mere presence of OTP words.
4. `test_golden_url.py` — IP host, deep subdomain, brand-in-subdomain, hyphens, punycode, each shortener, `@`, credentials, http, port, long/encoded query, redirect + exfil params, path keywords, risky-host hit (each: band + codes).
5. `test_benign_urls.py` — official bank/utility domains SAFE.
6. `test_no_network.py` — URL + message + QR analyzers import no `socket`/`httpx`/`requests`/`urllib.request`/`opencv` network paths; shortener case resolved without traffic (monkeypatched socket raising).
7. `test_qr_classification.py` — six classes incl. edge cases (empty, binary, `upi://` case variants).
8. `test_upi_extraction.py` — full + partial + malformed params; `am` non-numeric → None.
9. `test_qr_routing.py` — URL-in-QR yields `url.*` reasons; text-in-QR yields `message.*`; UPI-in-QR yields payment-family codes.
10. `test_qr_upload_limits.py` — >5 MB → 413; wrong magic → 422; pixel-bomb dims → 413; corrupt bytes → 200 + `unable_to_verify` (never 500).
11. `test_decode_authority.py` — image present + conflicting client `payload` → verdict follows server decode.
12. `test_qr_seen.py` — first `new` + row; rescan `previously_seen` count 2 same `first_seen_at`; variant payloads same hash; corrupt → no row.
13. `test_new_qr_is_not_safe` — low-score `new` QR carries `qr.seen_new` reason + mandated copy; no safety wording tied to seen-status anywhere in response.
14. `test_fusion_identity` — all Slice 2 goldens through `run.py` satisfy the §3.1 identity (payment regression).
15. `test_fusion_determinism` + `test_cross_type_composition` (message-with-URL; QR+payment_context).
16. `test_discriminated_union` — valid combos per type; missing/wrong-block/extra-block/`payment_context`-with-payment combos → 422 envelope.
17. `test_history_type_filter` + `test_stats_span_types` + `test_qr_seen_audit_once`.
18. `test_reasons_invariant_all_types` — every non-SAFE response has ≥1 reason.
19. Keep all 31 Slice 2 tests green unmodified (payment files untouched; `test_persistence_audit` may gain cases, never edits).
20. `test_old_rows_with_new_fields` — Slice 1/2 rows validate against the extended contract.

Frontend (`web/src`, Vitest):
1. Four mode submits send the correct discriminated payloads (file→base64 path stubbed at `lib/qr.ts` boundary; pasted-payload path direct).
2. Oversized/wrong-type file blocked client-side with message; decoder never invoked.
3. Result renders `EvidencePanel` (URLs, phrases, decoded payload, parsed UPI table) and `SeenStatusBadge` for all three QR statuses incl. the NEW≠SAFE note.
4. History type chips issue `type=` queries; combined level+type works.
5. Dashboard BY TYPE row matches the mocked list; existing sections unchanged.
6. Audit renders `QR_SEEN` entries; chain verify still works.
7. `tsc --noEmit` clean; `vite build` succeeds.

Test-data rule: QR fixtures generated at test time with `qrcode[pil]` (new dev-only dep); no binary blobs committed; corpora are small inline literals with a one-line provenance comment each.

## 21. Manual Verification Plan

Record command output + screenshots. SQLite stands in for Postgres (existing deviation); Postgres remains the target.

1. Message: paste `"Your account will be blocked in 10 minutes. Verify OTP now."` → HIGH with urgency + credential reasons and matched phrases shown.
2. Benign: paste a bank EMI-debited SMS → SAFE, no reasons beyond informational.
3. URL: `http://paypal.com.secure-login.xyz/verify?email=x` → HIGH with brand-in-subdomain + exfil-param reasons; confirm no outbound traffic (server has no route to fetch; note the FW/proxy log if available, else cite the no-network test).
4. Shortener: paste a `bit.ly` link → shortener reason; verdict does not resolve it (evidence shows the raw URL only).
5. QR upload: valid UPI QR image → decoded payload + parsed fields in evidence, verdict with reasons.
6. Rescan the same QR → `previously_seen` with first-seen date and count 2. Fresh QR → `new` with the explicit not-safe note.
7. Corrupt/blank image → `unable_to_verify` gracefully; 20 MB file → clean 413 rejection.
8. Payment regression: the three `DEVELOPER_GUIDE.md` §14 demos → unchanged bands (SAFE/MEDIUM/HIGH).
9. History mixed types with both chip rows; dashboard totals + BY TYPE match; audit shows `SCAN_SUBMITTED` + one `QR_SEEN`.
10. Full suites green; screenshots of the four input modes and the new result elements.

## 22. Files to Create

**Backend:** `app/pipeline/{__init__ (exists — extend? No: new files only) normalize,signals,fuse,explain}.py` — concretely: `normalize.py`, `signals.py`, `fuse.py`, `explain.py`; `app/pipeline/run.py`; `app/analyzers/base.py`, `message_analyzer.py`, `url_analyzer.py`, `qr_analyzer.py`; `app/services/qr_seen_service.py`; `app/repositories/qr_seen.py`; `alembic/versions/0002_qr_seen.py`; `app/data/risky_hosts.json`; tests `test_normalization.py`, `test_golden_message.py`, `test_benign_messages.py`, `test_golden_url.py`, `test_benign_urls.py`, `test_no_network.py`, `test_qr_classification.py`, `test_upi_extraction.py`, `test_qr_routing.py`, `test_qr_upload_limits.py`, `test_decode_authority.py`, `test_qr_seen.py`, `test_new_qr_safe.py`, `test_fusion_identity.py`, `test_cross_type.py`, `test_discriminated_union.py` (may be consolidated — minimum one file per numbered item in §20, no mega-files over ~250 lines).
**Frontend:** `components/{ScanTypeSelector,EvidencePanel,SeenStatusBadge}.tsx`, `lib/qr.ts`, tests `TransactionPage` additions (mode submits), `ResultPage` additions (evidence/seen), `HistoryPage` additions (type chips), `DashboardPage` additions (by-type), `AuditPage` additions (QR_SEEN).
**Config/deps:** `opencv-python-headless` → `requirements.txt`; `qrcode[pil]` → `requirements-dev.txt`; `jsqr` → `web/package.json` (+ lockfiles via installs).

## 23. Files to Modify

| File | Current | Change |
|---|---|---|
| `backend/app/schemas/analyze.py` | payment-only contract | + Message/Url/Qr/PaymentContext inputs, generalized validator, `Evidence.parsed_qr` + `payload_class` |
| `backend/app/analyzers/payment_analyzer.py` | builds reasons inline, sums internally | emit `Signal`s; move action table to `explain.py`; scoring math unchanged per the §3.1 identity |
| `backend/app/api/routes/analyze.py` | payment dispatch | dispatch via `run.py`; per-type persistence + `input_echo`; QR seen lookup; `QR_SEEN` audit on first sight |
| `backend/app/api/routes/scans.py` | `type` accepts payment only | accept all four; per-type labels |
| `backend/app/repositories/scans.py` | limit/level/type filters | unchanged behaviour (already generic) — touch only if needed |
| `backend/app/db/models.py` | Scan + AuditLog | + `QrSeen` model (additive) |
| `backend/app/config.py` + `.env.example` | `slice-2`, no QR flags | `PIPELINE_VERSION=slice-3`, `STORE_QR_PAYLOADS=true`, `QR_MAX_MB=5`, `QR_MAX_MEGAPIXELS=12` |
| `backend/tests/test_persistence_audit.py` | green | may gain type/audit cases; existing cases untouched |
| `web/src/pages/TransactionPage.tsx` | payment form | + selector + per-mode inputs + union submit |
| `web/src/pages/ResultPage.tsx` | gauge/reasons/action/summary | + EvidencePanel + SeenStatusBadge; Make-Payment hidden for non-payment |
| `web/src/pages/HistoryPage.tsx` | level chips | + type chips row |
| `web/src/pages/DashboardPage.tsx` | stats + charts | + BY TYPE row (client-derived) |
| `web/src/pages/AuditPage.tsx` | labels + refresh | + `QR_SEEN` label |
| `web/src/api/analyze.ts` + `types.ts` | payment-only types | union types; `fetchScans` already generic |
| `vh-s02/README.md` | Slice 2 runbook | Slice 3 behaviour: modes, seen semantics, upload limits, new flags |

**Do not touch:** `pipeline/rules.py`, `pipeline/thresholds.py`, `categories.py` values, `db` existing models, `audit_service.py`, `main.py` (except registering nothing new — no new routers needed), `health.py`, `stats.py`, `LoginPage.tsx`, token CSS, `gates.ts` logic, `lib/balance.ts`, `0001_initial.py`.

## 24. Scope Boundaries

**In:** §§5–19. **Out (deferred to Slice 4 or later, must not leak):**
ML, ML artifacts/registry, LLM/advisory/provider/prompts/external AI APIs, real auth, `users` table, server rate limiting, Docker, CI, deployment, hardening, push notifications, live URL reputation, DNS, WHOIS, URL fetching, visual QR/logo forensics, real payment execution, new top-level pages/routes, new design tokens, animation/icon libraries beyond existing, component libraries beyond `jsqr`.

## 25. Risks and Mitigations

| # | Risk | Mitigation |
|---|---|---|
| 1 | Slice 3 is the largest slice (4 analyzers + decode + seen + fusion + UI) | Internal order: QR plumbing + seen first (differentiator), then URL, then message; each registry-additive; app shippable at every commit; payment path tested continuously. |
| 2 | OpenCV decode quality on real photos | `unable_to_verify` is a first-class, tested outcome — misses degrade, never crash or mis-score; fixture tests use clean generated codes, manual verification uses one real photo. |
| 3 | opencv wheel weight (~50 MB) / install friction | Headless build, pinned version, documented; missing OpenCV is a loud startup failure (never silent degradation into `unable_to_verify`); unreadable images remain routine `unable_to_verify` outcomes. |
| 4 | Payment regression during refactor | `test_fusion_identity` + untouched golden file run on every change; payment analyzer math moves zero lines except signal emission shape. |
| 5 | False positives on benign messages/URLs | Benign corpora with a no-false-positive budget; keyword caps; impersonation requires brand+request co-occurrence, never brand alone. |
| 6 | NEW≠SAFE misread by users/judges | Triple enforcement (§11): fixed copy + informational reason + copy test; demo script says the line aloud. |
| 7 | Scope leak into Slice 4 | §24 + tripwires (§Scope Tripwires); validator rejects non-implemented types mechanically. |
| 8 | Schema creep (`input_echo`, new evidence fields) | All additions optional-with-defaults; old-row tolerance tests; no new non-nullable columns except `qr_seen` PK table. |
| 9 | ReDoS in new regexes | Linear-only constructions; review checklist item; existing suite time-boxed (pytest duration assertion optional). |
| 10 | Reference transcription (clean-room) | Tables/regexes authored from the plan's normative lists; reviewers verify no upstream file opened beyond cited behaviour. |

## 26. Rollback Strategy

- Branch `slice/3-detection`; Slice 2 tag is the restore point (`git checkout slice-2` / `git revert <range>`).
- Branch `slice/3-detection`; Slice 2 tag is the restore point (`git checkout slice-2` / `git revert <range>`). No feature-flag configuration is added in Slice 3: rollback is by revert, not by flags.
- `0002_qr_seen` is additive: reverting code leaves the table harmlessly unused; `alembic downgrade -1` available with documented seen-data loss.
- Frontend additions are additive components + page edits; revert cleanly.
- Worst case: delete-and-restore from the Slice 2 tag; `sentinelpay-main/` never at risk.

## 27. Slice 3 Definition of Done

- [ ] Four input types score through one pipeline with ordered reasons, evidence, and type-aware safe actions.
- [ ] QR upload → server-authoritative decode → classification → routing → seen-status, with hardening tests green and no 500 on hostile input.
- [ ] Previously-seen/new/unable-to-verify behave per §11 with non-misleading copy; NEW≠SAFE triple-enforced.
- [ ] Fusion deterministic; payment-only path satisfies the §3.1 identity (all 10 goldens + Slice 2 suite green unmodified).
- [ ] Discriminated contract validated (422 matrix green); old rows still read; stats/audit span types.
- [ ] Six screens recognisably SentinelPay; changes additive (selector, evidence, badge, type chips, by-type row, labels).
- [ ] Frontend suite + `tsc` + `vite build` green; manual verification (§21) recorded.
- [ ] No Slice 4 artefact (§Scope Tripwires clear); single migration `0002`; no new pages; no redesign.
- [ ] `sentinelpay-main/` unchanged; no upstream code/`.pkl`; README updated; scratch DBs removed.
- [ ] Git tag `slice-3` (only if the repo is initialised for tagging).

### Open Decisions

Genuinely blocking approval (recommendations included; work proceeds on defaults if unanswered):

1. **Server decode library: `opencv-python-headless`?** Recommended yes (≈50 MB pinned wheel, no system deps, `QRCodeDetector` adequate with `unable_to_verify` fallback). Alternative `pyzbar` rejected (Windows zbar installer risk). Confirm or propose an alternative before backend QR work starts.
2. **QR image transport: base64-in-JSON (recommended) vs multipart?** Base64 keeps one content-type, one validator, trivial tests at 33% overhead — fine under the 5 MB cap. Multipart only if reviewers object.
3. **`STORE_QR_PAYLOADS` default true?** Recommended true for Slice 3 demo richness (evidence shows decoded payload), with Slice 4 redaction review. If privacy posture requires, default false now (evidence keeps class + preview only).
4. **Risky-host list ownership:** seed with ~20 well-known phishing-pattern hosts as curated demo/test heuristic data (a match is an indicator, never proof of maliciousness), or ship empty with structure only? Recommended: small seeded list (demonstrable), clearly labelled curated-demo-data.
5. **Payment-context scope:** allow optional `payment_context` on message/url/qr requests in Slice 3 (recommended, minimal: amount/balance/payee-name), or defer composition to Slice 4? Deferring simplifies validation but weakens the "before money is sent" story for QR.

### Three Approaches

**A. QR decoding strategy.**
- Approach A — client-only decode; server trusts `payload`. Cheapest, no new backend dep; but server authority is lost and a hostile client can inject arbitrary payloads as "decoded". Rejected.
- Approach B — server-only decode; client sends bytes blind. Full authority; but no instant preview, worse UX, harder manual testing. Rejected as sole path.
- Approach C — **chosen:** client previews via `jsqr` (instant feedback, no verdict), server re-decodes uploads via OpenCV as the verdict authority; client `payload` accepted only without an image. Reason: preserves UX and authority with a clear trust boundary, both paths tested.

**B. Generalized request schema.**
- Approach A — **chosen:** single `POST /api/analyze` with optional blocks + discriminated validator. One endpoint, one response, one history item type; matches migrationrun §6 and keeps History/Dashboard/Audit unified.
- Approach B — separate endpoints per type (`/api/analyze/message` …). More routes, four response shapes drifting apart, frontend branches everywhere. Rejected.
- Approach C — single opaque `input: {kind, blob}` with runtime sniffing. Saves schema lines, loses validation errors and contract clarity. Rejected.

**C. Fusion architecture.**
- Approach A — **chosen:** additive weighted sum over one signal list (`fuse.py`), payment identity invariant tested. Explainable, order-stable, single place to tune.
- Approach B — upstream-style `max()` overlays per analyzer. Preserves old shape but hides contributions and breaks composability. Rejected.
- Approach C — decision-tree/rules engine with branching. More expressive, untestable at this scale, over-engineering. Rejected.

**D. QR seen persistence.**
- Approach A — **chosen:** dedicated `qr_seen` table via `0002` (hash PK, lifecycle columns). Indexed lookups, clear ownership, additive migration.
- Approach B — `payload_hash` column on `scans` + distinct query. Touches the hot table, conflates scan records with aggregate state, awkward counts. Rejected.
- Approach C — in-memory dict. Loses data on restart, untestable across runs, useless for "previously seen". Rejected.

**E. Evidence representation.**
- Approach A — **chosen:** extend existing `Evidence` with optional `parsed_qr`/`payload_class` (defaults keep old rows valid). One shape for all types, frontend renders conditionally.
- Approach B — free-form `dict` evidence. No contract, untestable rendering. Rejected.
- Approach C — per-type evidence subtypes (discriminated union). Correct long-term, but churns the contract and all clients in Slice 3 for little demo gain. Deferred to Slice 4 if needed.

Expensive-to-reverse decisions flagged: `opencv-python-headless` dependency weight (§25.3); `qr_seen` table shape (PK choice is forever — hash-of-normalized-payload is the stable key); `Evidence` additive fields (contract promise to old rows); `STORE_QR_PAYLOADS` default (privacy posture).

### Scope Tripwires

Run after implementation; any hit is a scope failure blocking slice acceptance:

1. `rg -l "ml_analyzer|from app.ml|import llm|advisory provider|prompt_template|OPENAI_|ANTHROPIC_" backend/app web/src` → must be empty (the pre-existing disabled `Advisory` contract model is allowed; providers are not).
2. `rg -l "users|password_hash|Authorization.*Bearer|rate_limit|ratelimit" backend/app web/src` → empty (except comments explicitly marked Slice 4).
3. `ls backend/app/ml backend/app/llm backend/app/auth 2>/dev/null` → must not exist; `ls backend/alembic/versions` → exactly `0001_initial.py`, `0002_qr_seen.py`.
4. `rg "Dockerfile|docker-compose|\.github/workflows" vh-s02` → empty.
5. Routes audit: `@router` decorators limited to existing files + no new files under `api/routes/`; frontend `Route` list identical to Slice 2 (`/login /transaction /result/:id /dashboard /history /audit`).
6. Validator audit: `analysis_type` accepts exactly four values; non-payment blocks rejected as in Slice 2.
7. Dependency audit: `requirements.txt` adds only `opencv-python-headless`; `requirements-dev.txt` adds only `qrcode[pil]`; `package.json` adds only `jsqr`; no other new deps.
8. `sentinelpay-main/` file count still 164 and no `.pkl` path referenced anywhere in `vh-s02/`.


