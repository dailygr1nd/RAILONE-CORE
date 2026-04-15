# corridor_learning.py

CORRIDOR_MEMORY = {}


def _corridor_key(from_ccy, to_ccy):
    return f"{from_ccy}->{to_ccy}"


def learn_corridor(from_ccy, to_ccy, route_type, success, latency_ms):
    """
    Learns transaction behavior for a currency corridor.
    """

    key = _corridor_key(from_ccy, to_ccy)

    if key not in CORRIDOR_MEMORY:
        CORRIDOR_MEMORY[key] = {
            "attempts": 0,
            "successes": 0,
            "failures": 0,
            "avg_latency_ms": latency_ms,
            "preferred_route": route_type,
            "route_history": {}
        }

    corridor = CORRIDOR_MEMORY[key]

    corridor["attempts"] += 1

    if success:
        corridor["successes"] += 1
    else:
        corridor["failures"] += 1

    attempts = corridor["attempts"]

    # rolling latency average
    corridor["avg_latency_ms"] = (
        (corridor["avg_latency_ms"] * (attempts - 1)) + latency_ms
    ) / attempts

    # route history memory
    if route_type not in corridor["route_history"]:
        corridor["route_history"][route_type] = {
            "attempts": 0,
            "successes": 0
        }

    route_data = corridor["route_history"][route_type]
    route_data["attempts"] += 1

    if success:
        route_data["successes"] += 1

    corridor["preferred_route"] = get_best_historical_route(key)


def get_corridor_success_rate(from_ccy, to_ccy):
    key = _corridor_key(from_ccy, to_ccy)

    corridor = CORRIDOR_MEMORY.get(key)

    if not corridor:
        return 0.95  # optimistic default

    return corridor["successes"] / corridor["attempts"]


def get_best_historical_route(corridor_key):
    corridor = CORRIDOR_MEMORY.get(corridor_key)

    if not corridor:
        return "SMOVE"

    best_route = None
    best_score = -1

    for route, stats in corridor["route_history"].items():
        if stats["attempts"] == 0:
            continue

        score = stats["successes"] / stats["attempts"]

        if score > best_score:
            best_score = score
            best_route = route

    return best_route or "SMOVE"


def get_corridor_health(from_ccy, to_ccy):
    key = _corridor_key(from_ccy, to_ccy)

    corridor = CORRIDOR_MEMORY.get(key)

    if not corridor:
        return {
            "confidence": 0.5,
            "latency_score": 0.5,
            "preferred_route": "SMOVE"
        }

    success_rate = corridor["successes"] / corridor["attempts"]

    latency = corridor["avg_latency_ms"]

    if latency <= 700:
        latency_score = 1.0
    elif latency <= 1200:
        latency_score = 0.85
    elif latency <= 1800:
        latency_score = 0.65
    else:
        latency_score = 0.4

    confidence = round((success_rate * 0.7) + (latency_score * 0.3), 4)

    return {
        "confidence": confidence,
        "latency_score": latency_score,
        "preferred_route": corridor["preferred_route"]
    }


def print_corridor_learning():
    print("\n🌍 Corridor Learning Memory")
    print("-" * 40)

    for corridor, stats in CORRIDOR_MEMORY.items():
        success_rate = stats["successes"] / stats["attempts"]

        print(f"Corridor: {corridor}")
        print(f"Attempts: {stats['attempts']}")
        print(f"Success Rate: {success_rate:.2%}")
        print(f"Latency: {stats['avg_latency_ms']:.2f} ms")
        print(f"Preferred Route: {stats['preferred_route']}")
        print("-" * 40)