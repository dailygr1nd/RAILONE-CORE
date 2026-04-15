# corridor_learning.py

class CorridorLearningEngine:
    """
    RailOne adaptive learning layer.
    Updates corridor behavior based on transaction history.
    """

    def __init__(self):
        self.stats = {}

    # --------------------------
    # 1. LOG OUTCOME
    # --------------------------
    def log_transaction(self, result):
        path = result["best_path"]["path"]

        if path not in self.stats:
            self.stats[path] = {
                "attempts": 0,
                "successes": 0,
                "avg_latency": 0
            }

        record = self.stats[path]

        record["attempts"] += 1

        if result["best_path"]["success"]:
            record["successes"] += 1

        # update rolling latency
        record["avg_latency"] = (
            (record["avg_latency"] * (record["attempts"] - 1)
            + result["best_path"]["latency"])
            / record["attempts"]
        )

    # --------------------------
    # 2. GET UPDATED SUCCESS RATE
    # --------------------------
    def get_success_rate(self, path):
        if path not in self.stats:
            return 0.85  # default prior assumption

        record = self.stats[path]
        return record["successes"] / record["attempts"]

    # --------------------------
    # 3. FEEDBACK TO ROUTING SYSTEM
    # --------------------------
    def adjust_path_score(self, base_score, path):
        """
        Adjust routing score based on real-world performance.
        """

        success_rate = self.get_success_rate(path)

        return base_score * success_rate