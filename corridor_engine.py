# corridor_engine.py

import random
from corridor_fx_model import quote_conversion


class CorridorEngine:
    """
    Core RailOne corridor intelligence layer.
    Simulates how money moves across fragmented African rails.
    """

    def __init__(self, rails_registry, fx_model):
        self.rails = rails_registry
        self.fx = fx_model

    # --------------------------
    # 1. BUILD POSSIBLE PATHS
    # --------------------------
    def generate_paths(self, transaction):
        """
        Create possible execution paths across rails.
        """

        from_country = transaction["from_country"]
        to_country = transaction["to_country"]

        paths = []

        # Path 1: Bank-to-bank
        paths.append({
            "type": "BANK",
            "route": f"bank_{from_country} -> bank_{to_country}",
            "base_success_rate": 0.85,
            "base_latency": 300,
            "cost": 2.5
        })

        # Path 2: PSP mobile money
        paths.append({
            "type": "PSP",
            "route": f"mpesa/airtel route {from_country}->{to_country}",
            "base_success_rate": 0.93,
            "base_latency": 60,
            "cost": 1.0
        })

        # Path 3: Smove wallet bridge
        paths.append({
            "type": "SMOVE",
            "route": f"smove bridge {from_country}->{to_country}",
            "base_success_rate": 0.88,
            "base_latency": 180,
            "cost": 1.5
        })

        return paths

    # --------------------------
    # 2. SIMULATE PATH OUTCOME
    # --------------------------
    def simulate_path(self, path, transaction):
        """
        Simulate real-world behavior of a path.
        """

        amount = transaction["amount"]
        from_ccy = transaction["currency_from"]
        to_ccy = transaction["currency_to"]

        # FX conversion impact
        fx_result = self.fx.quote_conversion(amount, from_ccy, to_ccy)

        # Simulate success/failure
        success = random.random() < path["base_success_rate"]

        # Add noise (real-world uncertainty)
        latency = max(1, random.gauss(path["base_latency"], 30))
        cost = path["cost"]

        return {
            "path": path["route"],
            "success": success,
            "latency": latency,
            "cost": cost,
            "converted_amount": fx_result["converted_amount"],
            "fx_rate": fx_result["fx_rate"]
        }

    # --------------------------
    # 3. SCORE OUTCOME
    # --------------------------
    def score_result(self, result):
        """
        Convert outcome into a utility score.
        """

        if not result["success"]:
            return -1000  # heavy penalty for failure

        score = 0

        # lower latency = better
        score -= result["latency"] * 0.01

        # lower cost = better
        score -= result["cost"] * 5

        # higher converted value = better
        score += result["converted_amount"] * 0.1

        return score

    # --------------------------
    # 4. MAIN DECISION ENGINE
    # --------------------------
    def route_transaction(self, transaction):
        """
        Main RailOne decision function.
        """

        paths = self.generate_paths(transaction)

        best_path = None
        best_score = float("-inf")

        for path in paths:
            result = self.simulate_path(path, transaction)
            score = self.score_result(result)

            if score > best_score:
                best_score = score
                best_path = result

        return {
            "best_path": best_path,
            "score": best_score,
            "all_paths_tested": len(paths)
        }