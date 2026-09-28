# Payment Guardian

Detecting digital payment scams before money is sent. Paste a suspicious payment-related message and get a deterministic, explainable risk assessment with safe next steps.

## Overview

Payment scams usually arrive as ordinary-looking messages: fake refunds, prize claims, KYC threats, OTP requests, QR/link lures. Payment Guardian analyzes the message text through a deterministic pipeline — signal extraction, weighted risk scoring, and evidence-grounded explanation — and returns a risk level, score, and recommended safe actions via a FastAPI backend with a minimal web frontend.

## Features

- Message analysis via `POST /api/analyze`
- Deterministic scam-signal extraction (8 signal types: urgency, reward/prize, refund claim, payment request, OTP/PIN request, account/credential request, impersonation, scan-or-click action)
- Weighted risk scoring (0.00–1.00) with combination bonuses
- Risk levels: LOW / MEDIUM / HIGH / CRITICAL
- Explainable scoring (each score contribution cites its matched evidence)
- Evidence-grounded user explanations (every explanation quotes the matched text)
- Recommended safe actions per matched signal
- End-to-end frontend ↔ backend flow

## Architecture

```
User Message
    ↓
Signal Extraction (signal_extractor.py, 8 deterministic matchers)
    ↓
Risk Scoring (risk_scorer.py, weights + combination bonuses)
    ↓
Explanation / Safe Actions (explainer.py, templates grounded in observed signals)
    ↓
API (main.py → mock_analyzer.py coordinator, POST /api/analyze)
    ↓
Frontend (frontend/index.html)
```

`mock_analyzer.analyze()` is the coordinator: extractor → scorer → explainer. Scoring logic lives in `risk_scorer`, wording in `explainer`, never in the coordinator.

## Tech Stack

- Python 3.11+
- FastAPI, Uvicorn, Pydantic
- httpx, pytest, pytest-asyncio
- Plain HTML/JS frontend (no framework)

## Project Structure

```
payment-guardian/
├── backend/
│   ├── main.py             # FastAPI app, /api/analyze, serves frontend
│   ├── mock_analyzer.py    # Pipeline coordinator (extract → score → explain)
│   ├── signal_extractor.py # 8 deterministic signal matchers
│   ├── risk_scorer.py      # Weights, combination bonuses, risk levels
│   ├── explainer.py        # Evidence-grounded summaries, explanations, actions
│   └── requirements.txt
├── frontend/
│   └── index.html          # Paste-message → result UI
└── tests/
    ├── test_analyze_endpoint.py
    ├── test_signal_extractor.py
    ├── test_risk_scorer.py
    └── test_explainer.py
```

## Getting Started

Prerequisites: Python 3.11+.

```powershell
pip install -r backend/requirements.txt
```

Run the backend (serves the API and the frontend):

```powershell
cd backend
uvicorn main:app --reload --port 8000
```

Open the app: `http://localhost:8000/`

Run the tests (from the project root):

```powershell
pytest tests/ -v
```

## API

### `POST /api/analyze`

Request:

```json
{ "message": "Congratulations! You have received a refund. Scan the QR code immediately to claim it." }
```

Response:

```json
{
  "risk_level": "HIGH",
  "risk_score": 0.55,
  "signals": ["reward_or_prize (+0.15): congratulations", "..."],
  "recommended_action": "Multiple scam indicators detected. Do not proceed without independent verification.",
  "analyzed_by": "explainer_v1",
  "summary": "High risk: this message contains several warning signals. ...",
  "explanation": ["The message claims you have won ... (found: \"congratulations\"). ..."],
  "actions": ["Do not pay any fee or ..."]
}
```

Validation: empty messages return `400`; missing `message` field returns `422`; messages are limited to 2000 characters. `GET /api/health` returns `{"status": "ok"}`.

## Testing

```powershell
pytest tests/ -v
```

54 tests covering the endpoint, all 8 signal types, scorer weights/bonuses/level boundaries, and explainer grounding (every explanation quote must appear in scorer evidence; no certainty language like "definitely a scam" or "100% safe").

## Current Status

Completed through Slice 4: working frontend + FastAPI backend + `/api/analyze` (Slice 1), deterministic 8-signal extraction `signal_extractor_v1` (Slice 2), weighted explainable scorer `weighted_scorer_v1` (Slice 3), evidence-grounded explanation/action layer `explainer_v1` (Slice 4).

## Roadmap

Future work, not yet implemented:

- URL intelligence / reputation analysis
- QR payload analysis
- ML-based scoring
- LLM-assisted analysis
- Payment-context intelligence
- Additional signal sources

## Security / Limitations

The risk score is a heuristic severity indicator, not a calibrated probability and not a fraud determination. A signal firing means a keyword pattern matched, not that a scam is confirmed; no signal firing does not mean a message is safe. Known example: legitimate OTP delivery messages trigger `otp_or_pin_request`. Always verify through official channels. This project has no authentication, no persistence, and no real transaction analysis — do not use it as a production fraud decision system.
