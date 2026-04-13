# routing_metrics.py

ROUTE_METRICS = {
    "BANK_A": {
        "attempts": 0,
        "successes": 0,
        "failures": 0,
        "avg_latency_ms": 1000
    },
    "BANK_B": {
        "attempts": 0,
        "successes": 0,
        "failures": 0,
        "avg_latency_ms": 1200
    },
    "PSP": {
        "attempts": 0,
        "successes": 0,
        "failures": 0,
        "avg_latency_ms": 800
    },
    "BANK_FAIL": {
        "attempts": 0,
        "successes": 0,
        "failures": 0,
        "avg_latency_ms": 3000
    }
}


def record_route_result(route_type, success, latency_ms):
    """
    Update live telemetry after each transaction.
    """
    if route_type not in ROUTE_METRICS:
        return

    route = ROUTE_METRICS[route_type]

    route["attempts"] += 1

    if success:
        route["successes"] += 1
    else:
        route["failures"] += 1

    attempts = route["attempts"]

    # rolling average latency
    route["avg_latency_ms"] = (
        (route["avg_latency_ms"] * (attempts - 1)) + latency_ms
    ) / attempts


def get_live_success_rate(route_type):
    route = ROUTE_METRICS.get(route_type)

    if not route:
        return 0.5

    attempts = route["attempts"]

    if attempts == 0:
        return 0.95

    return route["successes"] / attempts


def get_latency_score(route_type):
    route = ROUTE_METRICS.get(route_type)

    if not route:
        return 0.5

    latency = route["avg_latency_ms"]

    # lower latency = higher score
    if latency <= 800:
        return 1.0
    elif latency <= 1500:
        return 0.8
    elif latency <= 2500:
        return 0.6
    else:
        return 0.3