from dataclasses import dataclass


@dataclass
class RouteCandidate:

    rail: str

    score: float

    health_score: float

    liquidity_score: float

    latency_score: float

    success_rate: float

    route_rank: int

    penalty_score: float = 0

    last_failure_reason: str | None = None

    metadata: dict | None = None