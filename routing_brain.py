# routing_brain.py

from telemetry import get_telemetry
from routing_metrics import (
    get_live_success_rate,
    get_latency_score
)


# --------------------------
# CORE INTELLIGENCE ENGINE
# --------------------------
def compute_rail_health(rail_type):
    """
    Combines:
    - expected telemetry (static baseline)
    - live metrics (real-world behavior)
    """

    telemetry = get_telemetry(rail_type)

    if not telemetry:
        return 0.5  # unknown rail fallback

    live_success = get_live_success_rate(rail_type)
    live_latency = get_latency_score(rail_type)

    # --------------------------
    # BASE EXPECTATION SCORE
    # --------------------------
    expected = telemetry["success_rate"] * 10

    # --------------------------
    # LIVE PERFORMANCE SCORE
    # --------------------------
    live = live_success * 10 + live_latency * 5

    # --------------------------
    # STABILITY FACTOR
    # --------------------------
    stability = 1 - telemetry["reversal_rate"]

    # --------------------------
    # FINAL HEALTH SCORE
    # --------------------------
    score = (expected * 0.4) + (live * 0.5) + (stability * 10 * 0.1)

    return round(score, 4)


# --------------------------
# RAIL COMPARATOR
# --------------------------
def compare_rails(rail_a, rail_b):
    score_a = compute_rail_health(rail_a)
    score_b = compute_rail_health(rail_b)

    if score_a > score_b:
        return rail_a
    return rail_b


# --------------------------
# RAIL RECOMMENDER (FOR ROUTER)
# --------------------------
def rank_candidate_rails(candidate_rails):
    """
    Input: list of rails
    Output: sorted rails (best first)
    """

    scored = []

    for rail in candidate_rails:
        score = compute_rail_health(rail["name"])
        scored.append((rail, score))

    return sorted(scored, key=lambda x: x[1], reverse=True)