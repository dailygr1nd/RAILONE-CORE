# routing.py
from telemetry import get_telemetry

RAILS = [
    "BANK_KE",
    "BANK_TZ",
    "BANK_UG",
    "PSP_KE",
    "PSP_TZ",
    "PSP_UG",
    "SMOVE"
]


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

    if account_id.startswith("SMV"):
        return "SMOVE"

    return "UNKNOWN"


def score_route(route_type, cross_border=False):
    metrics = get_telemetry(route_type)

    if not metrics:
        return -999

    score = 0

    score += metrics["success_rate"] * 50
    score += metrics["uptime"] * 20
    score += metrics["capacity_score"] * 15
    score += metrics["fx_strength"] * 10

    latency_penalty = metrics["avg_latency_ms"] / 1000
    reversal_penalty = metrics["reversal_rate"] * 100

    score -= latency_penalty
    score -= reversal_penalty

    if cross_border and route_type == "SMOVE":
        score += 8

    return round(score, 4)


def select_best_route(sender_acc, receiver_acc, cross_border=False):
    sender_rail = classify_rail(sender_acc)
    receiver_rail = classify_rail(receiver_acc)

    sender_score = score_route(sender_rail, cross_border)
    receiver_score = score_route(receiver_rail, cross_border)

    if sender_score >= receiver_score:
        return sender_rail

    return receiver_rail