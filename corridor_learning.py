# corridor_learning.py

class CorridorLearningEngine:
    """
    Learns from every transaction outcome.
    Improves RailOne decision intelligence over time.
    """

    def __init__(self):
        self.memory = {}

    def log(self, result):
        path = result["best_route"]["path"]

        if path not in self.memory:
            self.memory[path] = {
                "attempts": 0,
                "success": 0,
                "avg_latency": 0
            }

        record = self.memory[path]
        record["attempts"] += 1

        if result["best_route"]["success"]:
            record["success"] += 1

        record["avg_latency"] = (
            (record["avg_latency"] * (record["attempts"] - 1)
            + result["best_route"]["latency"])
            / record["attempts"]
        )

    def success_rate(self, path):
        if path not in self.memory:
            return 0.85

        r = self.memory[path]
        return r["success"] / r["attempts"]