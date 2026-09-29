# app/analyzers/payment_analyzer.py — validated payment -> verdict parts (Slice 3).
# Deterministic approximation of observable SentinelPay payment-analysis behaviour.
# NOT the original ML model. Pure function of its inputs: no clock, no random, no I/O.
# The hour-of-day signal is passed in by the caller; the route supplies
# server-trusted time in production (client timestamps never drive scoring there).
# Computation order and math are unchanged from Slice 2; signals now flow as
# Signal objects ordered through explain.order_signals.

from app.categories import CATEGORIES
from app.pipeline import explain, rules
from app.pipeline.signals import Signal
from app.pipeline.thresholds import classify
from app.schemas.analyze import PaymentInput

BASE_SCORE = 5
URGENT_POINTS = 50
INFO_POINTS = 25
PAYEE_UNVERIFIED_POINTS = 5


def _impact(points: int, *, high_at: int = 20, medium_at: int = 10) -> str:
    if points >= high_at:
        return "high"
    if points >= medium_at:
        return "medium"
    return "low"


def _sig(name: str, contribution: float, observation: str, title: str,
         impact: str, rank: int, value: float | None = None) -> Signal:
    return Signal(name=name, value=value, contribution=contribution,
                  observation=observation, title=title, impact=impact, rank=rank)


def collect_payment_signals(payment: PaymentInput, *, hour: int | None,
                            _ml: list = []) -> tuple[list[Signal], list[Signal], tuple]:
    """Build pre-ceiling and post-ceiling additive signals. Pure.

    Split mirrors Slice 2 computation order exactly: the drain ceiling and
    magnitude floor apply to the pre Base+ML+tier+category+hour+elevated sum;
    note and payee additions stack on top afterwards. Optional `_ml` signals
    fuse with the pre-ceiling base (bounded, traceable).

    Returns (pre_including_base, post, (ratio, floor, family, phrases)).
    """
    pre: list[Signal] = [Signal(
        name="payment.base", contribution=BASE_SCORE,
        observation="Starting score", title="Base score", impact="low", rank=99)]
    pre.extend(_ml)
    post: list[Signal] = []

    tier_points, tier_label = rules.amount_tier(payment.amount)
    if tier_points:
        pre.append(_sig(
            "payment.amount_tier", tier_points,
            f"Amount Rs.{payment.amount:g} crosses the {tier_label} tier",
            "Large transaction amount",
            _impact(tier_points, high_at=25, medium_at=15), 1, payment.amount))

    cat_points, known = rules.category_points(payment.merchant_category)
    profile = CATEGORIES[payment.merchant_category]
    if cat_points:
        pre.append(_sig(
            f"payment.category.{profile['key'].lower()}", cat_points,
            f"Category {payment.merchant_category} carries elevated risk",
            "Elevated-risk category", _impact(cat_points), 2,
            float(profile["risk_weight"])))

    h_points, band = rules.hour_points(hour)
    if h_points:
        pre.append(_sig(
            "payment.unusual_hour", h_points,
            f"Submitted at {hour:02d}:00 — unusual hour", "Unusual hour",
            "medium" if band == "night" else "low", 4, float(hour or 0)))

    ratio = rules.drain_ratio(payment.amount, payment.sender_balance)
    if ratio > rules.DRAIN_ELEVATED_RATIO and ratio <= rules.DRAIN_CEILING_RATIO:
        pre.append(_sig(
            "payment.balance_drain_elevated", rules.DRAIN_ELEVATED_POINTS,
            f"Uses {ratio * 100:.0f}% of the sender balance",
            "Large share of balance", "medium", 3, ratio))

    floor = rules.magnitude_floor(payment.amount)
    family, phrases = rules.note_hits(payment.note)
    if family == "urgent":
        post.append(_sig(
            "payment.note.urgent", URGENT_POINTS,
            f"Note contains pressure words: {', '.join(phrases)}",
            "Pressure language in note", "high", 3))
    elif family == "info":
        post.append(_sig(
            "payment.note.credential", INFO_POINTS,
            f"Note contains verification words: {', '.join(phrases)}",
            "Verification language in note", "medium", 3))

    if rules.payee_unverified(payment.payee_name):
        post.append(_sig(
            "payment.payee_unverified", PAYEE_UNVERIFIED_POINTS,
            "Payee name not provided — cannot confirm recipient",
            "Unverified payee", "low", 5))

    return pre, post, (ratio, floor, family, phrases, payment.amount)


def finish_payment_verdict(pre: list[Signal], post: list[Signal],
                           aux: tuple) -> dict:
    """Fuse pre-ceiling base, apply Slice 2 ceilings in order, stack post."""
    from app.pipeline.fuse import fuse
    ratio, floor, family, phrases, amount = aux
    score = fuse(pre)
    fired = [s for s in pre if s.name != "payment.base"]
    if ratio > rules.DRAIN_CEILING_RATIO:
        score = max(score, rules.DRAIN_CEILING_SCORE)
        fired.append(_sig(
            "payment.balance_drain", rules.DRAIN_CEILING_SCORE,
            f"Uses {ratio * 100:.0f}% of the sender balance",
            "Drains the sender balance", "high", 0, ratio))
    if floor > score:
        score = floor
        fired.append(_sig(
            "payment.amount_magnitude", floor,
            "Amount approaches the UPI limit",
            "Amount Rs.{0:g} approaches the Rs.200,000 limit".format(amount), "medium", 0, amount))
    for s in post:
        score += s.contribution
        fired.append(s)
    score = max(0, min(100, round(score)))
    level = classify(score)
    ordered = explain.order_signals(fired)
    action = explain.select_action(level, "payment")
    matched = sorted(set(phrases)) if family else []
    return {
        "risk_score": score,
        "risk_level": level,
        "reasons": [s.to_reason() for s in ordered],
        "signals": [pre[0].to_dict()] + [s.to_dict() for s in ordered],
        "evidence": explain.build_evidence(matched_phrases=matched),
        "recommended_action": action,
    }


def analyze_payment(payment: PaymentInput, *, hour: int | None) -> dict:
    """Score a validated payment. Returns verdict parts (no ids, no timestamps)."""
    pre, post, aux = collect_payment_signals(payment, hour=hour)
    return finish_payment_verdict(pre, post, aux)


def payment_context_signals(ctx) -> list[Signal]:
    """Additive signals for an attached payment context (message/url/qr analyses).

    Partial information: no ceilings here — ceilings belong to standalone
    payment verdicts only. Same tables, additive form.
    """
    out: list[Signal] = []
    if ctx is None:
        return out
    if ctx.amount is not None:
        tier_points, tier_label = rules.amount_tier(ctx.amount)
        if tier_points:
            out.append(_sig(
                "payment_context.amount_tier", tier_points,
                f"Linked amount Rs.{ctx.amount:g} crosses the {tier_label} tier",
                "Linked payment amount",
                _impact(tier_points, high_at=25, medium_at=15), 1, ctx.amount))
        floor = rules.magnitude_floor(ctx.amount)
        if floor >= 50:
            out.append(_sig(
                "payment_context.amount_magnitude", 20,
                f"Linked amount Rs.{ctx.amount:g} approaches the Rs.200,000 limit",
                "Linked amount near the UPI limit", "medium", 1, ctx.amount))
    if ctx.amount is not None and ctx.sender_balance is not None:
        ratio = rules.drain_ratio(ctx.amount, ctx.sender_balance)
        if ratio > rules.DRAIN_CEILING_RATIO:
            out.append(_sig(
                "payment_context.balance_drain", 30,
                f"Linked payment uses {ratio * 100:.0f}% of the balance",
                "Linked payment drains balance", "high", 0, ratio))
        elif ratio > rules.DRAIN_ELEVATED_RATIO:
            out.append(_sig(
                "payment_context.balance_drain", 15,
                f"Linked payment uses {ratio * 100:.0f}% of the balance",
                "Linked payment uses large share", "medium", 3, ratio))
    if ctx.payee_name is not None and rules.payee_unverified(ctx.payee_name):
        out.append(_sig(
            "payment_context.payee_unverified", PAYEE_UNVERIFIED_POINTS,
            "Linked payee name not provided — cannot confirm recipient",
            "Linked payee unverified", "low", 5))
    return out

