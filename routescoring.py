from routing_metrics import (
    get_live_success_rate,
    get_latency_score
)


def score_route(route, amount, available_mirrored_available_state):

    route_type = route["type"]

    if amount > available_mirrored_available_state:
        return -999

    success_rate = get_live_success_rate(route_type)
    latency_score = get_latency_score(route_type)

    # --------------------------
    # BASE ROUTE VALUE
    # --------------------------
    base_score = success_rate * 10

    # --------------------------
    # LATENCY IMPACT
    # --------------------------
    latency_penalty = (1 - latency_score) * 5

    # --------------------------
    # ROUTE TYPE BEHAVIOR MODEL
    # --------------------------
    if "BANK" in route_type:
        stability_bonus = 2.0
        volatility_penalty = 0.2

    elif "PSP" in route_type:
        stability_bonus = 1.0
        volatility_penalty = 0.6

    elif "SMOVE" in route_type:
        stability_bonus = 1.5
        volatility_penalty = 1.2  # FX + IMT risk

    else:
        stability_bonus = 0
        volatility_penalty = 1.0

    # --------------------------
    # AMOUNT SCALING (VERY IMPORTANT)
    # large transactions behave riskier
    # --------------------------
    size_penalty = min(amount / 1_000_000, 2) * 0.5

    # --------------------------
    # FINAL SCORE
    # --------------------------
    final_score = (
        base_score
        + stability_bonus
        - latency_penalty
        - volatility_penalty
        - size_penalty
    )

    return round(final_score, 3)