# VH-S02 Demo Script (Slice 4) — timed, offline-capable

**Setup (one command):** `docker compose up --build` (or local: backend
`alembic upgrade head` + `uvicorn`, frontend `npm run dev`). Seed first:
`python backend/scripts/seed.py` (or compose seed step). Total ~7 minutes.
Recording a backup video and securing venue hosting are manual final-demo
tasks for a human — this script is what gets recorded.

## 0. Health (30s)
- `GET /api/health` → `status ok`, `model_backend: none`, `advisory: disabled`,
  `auth_required: true`. Point out the disclosure: the app tells you what is on.

## 1. Safe payment (45s)
- Login as the seeded demo user. Transaction tab: ₹150, Groceries,
  `shop@grocery`, balance ₹5,000 → **SAFE (5)**, no reasons.
- "A quiet check stays quiet."

## 2. Suspicious payment (45s)
- ₹3,500, Electronics, `vendor@upi` → **MEDIUM (35)** with amount + category reasons.

## 3. High-risk payment (60s)
- ₹12,000, Travel, `unknown@upi`, 02:30 context → **HIGH (75)** with four reasons.
- Open History: three scans listed. Open Dashboard: tiles + charts agree.

## 4. Scam message (45s)
- Message tab: "Your account will be blocked in 10 minutes. Verify OTP now."
  → **HIGH (80)** with urgency/credential/deadline reasons + matched phrases.

## 5. Phish link (45s)
- Link tab: `http://paypal.com.secure-login.xyz/verify?email=x` → **HIGH (75)**.
- "Nothing was fetched or opened — analysis is fully static."

## 6. QR + duplicate (90s)
- QR tab: upload a UPI QR image → decoded payload + parsed fields shown.
- Scan it again → **Previously seen**, count 2, same first-seen date.
- "A new code is not a safe code — the badge says so explicitly."

## 7. Tamper evidence (60s)
- Edit one `audit_log` row via SQL client → chain dot turns red, breach dialog
  names the entry → restore → green. Audit page Verify + export.

## 8. Honest intelligence (60s, optional)
- Health shows `model_backend: none`, advisory disabled. If enabled for the
  run: show version disclosure (`synthetic-v1`), one golden re-run holding its
  band, and the labelled advisory note. "Off by default, disclosed when on."

**Close:** "Deterministic, explainable, auditable — check before you pay."
