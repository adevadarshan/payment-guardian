# Slice 4 coordinator — wires signal_extractor to risk_scorer + explainer; scoring lives in risk_scorer, wording in explainer, not here.

try:
    import signal_extractor
    import risk_scorer
    import explainer
except ImportError:  # support `from backend.main import app` from project root
    from backend import signal_extractor, risk_scorer, explainer


def analyze(message: str) -> dict:
    signals = signal_extractor.analyze(message)
    result = risk_scorer.score(signals)
    explanation = explainer.build_explanation(signals, result["risk_level"], result["risk_score"])
    return {**result, **explanation, "analyzed_by": "explainer_v1"}
