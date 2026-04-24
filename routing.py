# routing.py

from routing_brain import compute_rail_health
from routescoring import score_route
from liquidity_engine import check_liquidity


def classify_rail(account_id):
    if account_id.startswith("BANK_KE"):
        return "BANK_KE"
    if account_id.startswith("BANK_TZ"):
        return "BANK_TZ"
    if account_id.startswith("BANK_UG"):
        return "BANK_UG"

    if account_id.startswith("PSP_MPESA_KE") or account_id.startswith("PSP_AIRTEL_KE"):
        return "PSP_KE"

    if account_id.startswith("PSP_MPESA_TZ") or account_id.startswith("PSP_AIRTEL_TZ"):
        return "PSP_TZ"

    if account_id.startswith("PSP_AIRTEL_UG"):
        return "PSP_UG"

    if account_id.startswith("SMOVE"):
        return "SMOVE"

    return "UNKNOWN"


# --------------------------------
# 🔥 SMART ROUTING
# --------------------------------
def get_best_rail(candidate_rails, amount, currency, cross_border=False):
    best = None
    best_score = -999

    for rail in candidate_rails:

        # --------------------------------
        # LIQUIDITY CHECK (HARD FILTER)
        # --------------------------------
        has_liquidity, _ = check_liquidity(
            route_type=rail,
            currency=currency,
            amount=amount
        )

        if not has_liquidity:
            continue  # 🚫 cannot use this rail

        # --------------------------------
        # HEALTH SCORE
        # --------------------------------
        health_score = compute_rail_health(rail)

        # --------------------------------
        # FINAL SCORING
        # --------------------------------
        route_obj = {"type": rail}

        final_score = score_route(
            route=route_obj,
            amount=amount,
            available_balance=1_000_000  # liquidity already checked
        )

        # cross-border bias
        if cross_border and rail == "SMOVE":
            final_score += 2

        # combine intelligence + scoring
        total_score = health_score + final_score

        if total_score > best_score:
            best_score = total_score
            best = rail

    return best or "SMOVE"  # fallback