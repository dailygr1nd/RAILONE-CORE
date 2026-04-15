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
