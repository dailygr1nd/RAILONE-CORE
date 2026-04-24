# corridor_engine.py

from routing import classify_rail
from routing_brain import compute_rail_health
from corridor_fx_model import quote_conversion
from corridor_learning import (
    get_corridor_health,
    get_best_historical_route
)
from corridor_pricing_engine import calculate_pricing
from liquidity_engine import check_liquidity


def build_corridor(sender_account, receiver_account, amount, sender_ccy, receiver_ccy):

    sender_rail = classify_rail(sender_account)
    receiver_rail = classify_rail(receiver_account)

    candidate_rails = list(set([sender_rail, receiver_rail, "SMOVE"]))

    corridor_key = f"{sender_ccy}->{receiver_ccy}"
    learning_health = get_corridor_health(sender_ccy, receiver_ccy)
    preferred_route = get_best_historical_route(corridor_key)

    fx_result = quote_conversion(amount, sender_ccy, receiver_ccy)

    candidates = []

    for rail in candidate_rails:

        # --------------------------------
        # LIQUIDITY FILTER
        # --------------------------------
        has_liquidity, _ = check_liquidity(
            route_type=rail,
            currency=sender_ccy,
            amount=amount
        )

        if not has_liquidity:
            continue

        # --------------------------------
        # BASE HEALTH
        # --------------------------------
        health_score = compute_rail_health(rail)

        # --------------------------------
        # PRICING (THIS IS NEW 🔥)
        # --------------------------------
        pricing = calculate_pricing(
    amount=amount,
    from_ccy=sender_ccy,
    to_ccy=receiver_ccy,
    route_type=rail,
    fx_rate=fx_result["fx_rate"]   # 🔥 ADD THIS
)

        margin = pricing["margin"]          # your profit
        cost = pricing["route_fee"]         # rail cost

        # --------------------------------
        # PROFIT SCORE
        # --------------------------------
        profit_score = (margin - cost) / max(amount, 1)

        # --------------------------------
        # LIQUIDITY STRESS PENALTY
        # --------------------------------
        liquidity_penalty = 0.2 if rail != "SMOVE" else 0.1

        # --------------------------------
        # FINAL SCORE
        # --------------------------------
        score = (
            health_score * 0.5
            + profit_score * 10
            + learning_health["confidence"] * 2
        )

        if rail == preferred_route:
            score += 1.5

        score -= liquidity_penalty

        candidates.append({
            "rail": rail,
            "type": rail,
            "score": round(score, 4),
            "margin": margin,
            "cost": cost,
            "converted_amount": fx_result["converted_amount"],
            "fx_rate": fx_result["fx_rate"]
        })

    # --------------------------------
    # FALLBACK
    # --------------------------------
    if not candidates:
        fallback = {
            "rail": "SMOVE",
            "type": "SMOVE",
            "score": 0,
            "margin": 0,
            "cost": 0,
            "converted_amount": fx_result["converted_amount"],
            "fx_rate": fx_result["fx_rate"]
        }

        return {
            "candidates": [fallback],
            "best_route": fallback
        }

    best_route = max(candidates, key=lambda x: x["score"])

    return {
        "candidates": candidates,
        "best_route": best_route
    }