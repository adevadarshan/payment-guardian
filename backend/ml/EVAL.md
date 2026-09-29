# ML Evaluation — synthetic-v1 (Slice 4)

## What this model is

A logistic regression trained to **approximate our own deterministic scorer**
on synthetic variations of it. It adds **no independent fraud knowledge**.
Its purpose is to prove the ML integration path end-to-end (train → artifact
→ checksum-verified load → bounded signal → disclosed version) — not to
detect fraud better than the rules.

**Do not cite these numbers as fraud-detection performance.** They measure how
faithfully the model mimics the scorer on synthetic data, nothing more.

## Methodology

- Generator: `backend/ml/train.py`, fixed seed `7`.
- Data: programmatic grid (14 amounts × 10 categories × 6 hours × sampled
  notes/payees/balances) = 840 rows. Labels: deterministic scorer band,
  SAFE → 0, MEDIUM/HIGH → 1.
- Split: 80/20 stratified train/test, `random_state=7`. The test split never
  trains the model.
- Golden corpora (`test_golden_*.py`) are regression/smoke tests, NOT the
  evaluation set. They overlap the generator's input space by construction,
  so golden agreement measures consistency, not generalization.
- Features: `FEATURES_V1` (9 numeric, documented in `app/ml/features.py`).

## Results (held-out synthetic test split, n=168)

- accuracy: 0.9405
- auc: 0.9896

Interpretation: the linear model tracks the rule bands closely on synthetic
data. Residual error concentrates near the 35/75 decision boundaries, where a
smooth probability necessarily disagrees with hard thresholds.

## Production behavior

- Default `MODEL_BACKEND=none`: the model never loads, `model.backend`
  discloses `"none"`, UI shows "Model: off".
- When enabled (`MODEL_BACKEND=synthetic-v1` + valid artifacts + checksum
  match): one bounded signal (`ml.risk`, ±15 max) fused through the normal
  path; version disclosed as `synthetic-v1`; every shift traceable.
- Any load failure (missing dir, checksum/schema mismatch, corrupt file)
  falls back to `none` and the API still starts.
