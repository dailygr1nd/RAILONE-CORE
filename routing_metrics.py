# routing_metrics.py

ROUTE_METRICS = {
    "BANK_KE": {"attempts": 0, "successes": 0, "failures": 0, "avg_latency_ms": 1200},
    "BANK_TZ": {"attempts": 0, "successes": 0, "failures": 0, "avg_latency_ms": 1400},
    "BANK_UG": {"attempts": 0, "successes": 0, "failures": 0, "avg_latency_ms": 1600},

    "PSP_KE": {"attempts": 0, "successes": 0, "failures": 0, "avg_latency_ms": 600},
    "PSP_TZ": {"attempts": 0, "successes": 0, "failures": 0, "avg_latency_ms": 700},
    "PSP_UG": {"attempts": 0, "successes": 0, "failures": 0, "avg_latency_ms": 800},

    "SMOVE": {"attempts": 0, "successes": 0, "failures": 0, "avg_latency_ms": 1800},
}


def record_route_result(route_type, success, latency_ms):
    route = ROUTE_METRICS.get(route_type)
    if not route:
        return

    route["attempts"] += 1

    if success:
        route["successes"] += 1
    else:
        route["failures"] += 1

    a = route["attempts"]

    route["avg_latency_ms"] = (
        (route["avg_latency_ms"] * (a - 1)) + latency_ms
    ) / a


def get_live_success_rate(route_type):
    route = ROUTE_METRICS.get(route_type)
    if not route or route["attempts"] == 0:
        return 0.93
    return route["successes"] / route["attempts"]


def get_latency_score(route_type):
    route = ROUTE_METRICS.get(route_type)
    if not route:
        return 0.5

    latency = route["avg_latency_ms"]

    if latency <= 700:
        return 1.0
    elif latency <= 1200:
        return 0.85
    elif latency <= 1800:
        return 0.65
    elif latency <= 2500:
        return 0.5
    return 0.3