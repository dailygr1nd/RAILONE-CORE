# corridor_engine.py

import random
from routing_brain import compute_rail_health
from routing_metrics import get_live_success_rate, get_latency_score
from corridor_fx_model import quote_conversion


class CorridorEngine:
    """
    RailOne Core Intelligence Layer
    Simulates real-world money movement across fragmented African rails.
    """

    def __init__(self):
        pass

    # --------------------------
    # BUILD EXECUTION OPTIONS
    # --------------------------
    def build_paths(self, sender_rail, receiver_rail):
        return [
            {
                "type": "DIRECT_BANK",
                "path": f"{sender_rail} -> {receiver_rail}",
                "base_success": 0.85,
                "latency": 300,
                "cost": 2.5
            },
            {
                "type": "PSP_ROUTE",
                "path": f"{sender_rail} -> PSP -> {receiver_rail}",
                "base_success": 0.93,
                "latency": 80,
                "cost": 1.0
            },
            {
                "type": "SMOVE_BRIDGE",
                "path": f"{sender_rail} -> SMOVE -> {receiver_rail}",
                "base_success": 0.88,
                "latency": 180,
                "cost": 1.5
            }
        ]

    # --------------------------
    # SIMULATE PATH
    # --------------------------
    def simulate(self, path, transaction):
        success_rate_boost = (
            get_live_success_rate(path["type"]) * 0.3
        )

        success_probability = min(
            path["base_success"] + success_rate_boost,
            0.99
        )

        success = random.random() < success_probability

        latency = max(1, random.gauss(path["latency"], 25))
        cost = path["cost"]

        fx = quote_conversion(
            transaction["amount"],
            transaction["currency_from"],
            transaction["currency_to"]
        )

        return {
            "path": path["path"],
            "type": path["type"],
            "success": success,
            "latency": latency,
            "cost": cost,
            "converted_amount": fx["converted_amount"]
        }

    # --------------------------
    # SCORE OUTCOME
    # --------------------------
    def score(self, result):
        if not result["success"]:
            return -1000

        score = 0
        score -= result["latency"] * 0.01
        score -= result["cost"] * 5
        score += result["converted_amount"] * 0.1

        return score

    # --------------------------
    # MAIN DECISION ENGINE
    # --------------------------
    def route(self, sender_rail, receiver_rail, transaction):
        paths = self.build_paths(sender_rail, receiver_rail)

        best = None
        best_score = float("-inf")

        for path in paths:
            result = self.simulate(path, transaction)
            score = self.score(result)

            if score > best_score:
                best_score = score
                best = result

        return {
            "best_route": best,
            "score": best_score,
            "paths_tested": len(paths)
        }