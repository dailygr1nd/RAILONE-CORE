"""Deterministic integer-only route eligibility and scoring."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .models import LinkStatus, RankedRoute, RouteCandidate, require_aware


@dataclass(frozen=True, slots=True)
class RouteScoreWeights:
    latency: int = 1_600
    congestion: int = 1_200
    liquidity: int = 1_700
    throughput: int = 1_200
    speed: int = 1_200
    cost: int = 1_800
    link: int = 1_300

    def __post_init__(self) -> None:
        values = (
            self.latency, self.congestion, self.liquidity, self.throughput,
            self.speed, self.cost, self.link,
        )
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise TypeError("route weights must be integers")
        if any(value < 0 for value in values) or sum(values) != 10_000:
            raise ValueError("route weights must be non-negative and sum to 10000")


class DeterministicRouteScorer:
    def __init__(self, weights: RouteScoreWeights | None = None) -> None:
        self.weights = weights or RouteScoreWeights()

    def rank(
        self,
        candidates: tuple[RouteCandidate, ...] | list[RouteCandidate],
        *,
        amount_minor: int,
        currency_from: str,
        currency_to: str,
        routing_budget_minor: int,
        at: datetime,
    ) -> tuple[RankedRoute, ...]:
        instant = require_aware("ranking timestamp", at)
        scored: list[tuple[RouteCandidate, int, tuple[tuple[str, int], ...]]] = []
        route_ids = [candidate.route_id for candidate in candidates]
        if len(route_ids) != len(set(route_ids)):
            raise ValueError("route_id must be unique within a planning request")
        for candidate in candidates:
            candidate.normalized()
            if not self._eligible(
                candidate,
                amount_minor=amount_minor,
                currency_from=currency_from,
                currency_to=currency_to,
                routing_budget_minor=routing_budget_minor,
                at=instant,
            ):
                continue
            components = self._components(
                candidate,
                amount_minor=amount_minor,
                routing_budget_minor=routing_budget_minor,
            )
            by_name = dict(components)
            weights = self.weights
            weighted = (
                by_name["latency"] * weights.latency
                + by_name["congestion"] * weights.congestion
                + by_name["liquidity"] * weights.liquidity
                + by_name["throughput"] * weights.throughput
                + by_name["speed"] * weights.speed
                + by_name["cost"] * weights.cost
                + by_name["link"] * weights.link
            ) // 10_000
            scored.append((candidate, weighted, components))

        scored.sort(key=lambda item: (-item[1], item[0].route_id))
        return tuple(
            RankedRoute(candidate=item[0], score_bps=item[1], component_scores=item[2], rank=index)
            for index, item in enumerate(scored, start=1)
        )

    @staticmethod
    def _eligible(
        candidate: RouteCandidate,
        *,
        amount_minor: int,
        currency_from: str,
        currency_to: str,
        routing_budget_minor: int,
        at: datetime,
    ) -> bool:
        return (
            candidate.link_status is not LinkStatus.DOWN
            and candidate.telemetry_observed_at <= at
            and candidate.telemetry_expires_at > at
            and candidate.currency_from.upper() == currency_from.upper()
            and candidate.currency_to.upper() == currency_to.upper()
            and candidate.min_amount_minor <= amount_minor <= candidate.max_amount_minor
            and candidate.liquidity_capacity_minor >= amount_minor
            and candidate.estimated_cost_minor <= routing_budget_minor
        )

    @staticmethod
    def _components(
        candidate: RouteCandidate,
        *,
        amount_minor: int,
        routing_budget_minor: int,
    ) -> tuple[tuple[str, int], ...]:
        latency = max(0, 10_000 - min(candidate.latency_ms, 10_000))
        congestion = 10_000 - candidate.congestion_bps
        liquidity = min(
            10_000,
            ((candidate.liquidity_capacity_minor - amount_minor) * 10_000)
            // amount_minor,
        )
        if routing_budget_minor == 0:
            cost = 10_000
        else:
            cost = max(
                0,
                10_000
                - (candidate.estimated_cost_minor * 10_000 // routing_budget_minor),
            )
        link = 10_000 if candidate.link_status is LinkStatus.UP else 4_000
        return (
            ("latency", latency),
            ("congestion", congestion),
            ("liquidity", liquidity),
            ("throughput", candidate.throughput_headroom_bps),
            ("speed", candidate.speed_bps),
            ("cost", cost),
            ("link", link),
        )
