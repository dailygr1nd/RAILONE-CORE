from telemetry import get_telemetry
from railhealth import get_success_rate


def score_route(route, amount, available_balance):
    route_type = route["type"]

    telemetry = get_telemetry(route_type)
    if not telemetry:
        return -999

    if amount > available_balance:
        return -999

    health_score = get_success_rate(route_type)
    latency_penalty = telemetry["avg_latency_ms"] / 1000
    reversal_penalty = telemetry["reversal_rate"] * 10
    base_score = telemetry["success_rate"] * 10

    final_score = (
        base_score
        + health_score
        - latency_penalty
        - reversal_penalty
    )

    return round(final_score, 3)
