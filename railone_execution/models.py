"""Immutable execution-planning and route-attempt domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from railone_contracts.models import require_minor_units, require_text
from railone_crypto.signature_service import SignatureEnvelope


def require_aware(name: str, value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def require_bps(name: str, value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if not 0 <= value <= 10_000:
        raise ValueError(f"{name} must be between 0 and 10000")
    return value


class LinkStatus(StrEnum):
    UP = "UP"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"


class PlanStatus(StrEnum):
    ACTIVE = "ACTIVE"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    FAILED = "FAILED"
    EXHAUSTED = "EXHAUSTED"
    FINALIZED = "FINALIZED"


class AttemptState(StrEnum):
    CREATED = "CREATED"
    FAILED = "FAILED"
    SUCCEEDED = "SUCCEEDED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


class FailureDisposition(StrEnum):
    RETRYABLE = "RETRYABLE"
    TERMINAL = "TERMINAL"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


@dataclass(frozen=True, slots=True)
class RouteCandidate:
    route_id: str
    source_institution_id: str
    destination_institution_id: str
    rail: str
    provider: str
    adapter: str
    currency_from: str
    currency_to: str
    min_amount_minor: int
    max_amount_minor: int
    latency_ms: int
    congestion_bps: int
    liquidity_capacity_minor: int
    throughput_headroom_bps: int
    speed_bps: int
    estimated_cost_minor: int
    link_status: LinkStatus
    telemetry_observed_at: datetime
    telemetry_expires_at: datetime

    def normalized(self) -> "RouteCandidate":
        require_text("route_id", self.route_id)
        require_text("source_institution_id", self.source_institution_id)
        require_text("destination_institution_id", self.destination_institution_id)
        require_text("rail", self.rail)
        require_text("provider", self.provider)
        require_text("adapter", self.adapter)
        require_text("currency_from", self.currency_from)
        require_text("currency_to", self.currency_to)
        minimum = require_minor_units(
            "min_amount_minor", self.min_amount_minor, allow_zero=True
        )
        maximum = require_minor_units("max_amount_minor", self.max_amount_minor)
        if minimum > maximum:
            raise ValueError("min_amount_minor cannot exceed max_amount_minor")
        require_minor_units("latency_ms", self.latency_ms, allow_zero=True)
        require_bps("congestion_bps", self.congestion_bps)
        require_minor_units(
            "liquidity_capacity_minor", self.liquidity_capacity_minor,
            allow_zero=True,
        )
        require_bps("throughput_headroom_bps", self.throughput_headroom_bps)
        require_bps("speed_bps", self.speed_bps)
        require_minor_units(
            "estimated_cost_minor", self.estimated_cost_minor, allow_zero=True
        )
        observed = require_aware("telemetry_observed_at", self.telemetry_observed_at)
        expires = require_aware("telemetry_expires_at", self.telemetry_expires_at)
        if expires <= observed:
            raise ValueError("telemetry expiry must be after observation")
        return self

    def to_payload(self) -> dict[str, Any]:
        self.normalized()
        return {
            "route_id": self.route_id,
            "source_institution_id": self.source_institution_id,
            "destination_institution_id": self.destination_institution_id,
            "rail": self.rail,
            "provider": self.provider,
            "adapter": self.adapter,
            "currency_from": self.currency_from.upper(),
            "currency_to": self.currency_to.upper(),
            "min_amount_minor": self.min_amount_minor,
            "max_amount_minor": self.max_amount_minor,
            "latency_ms": self.latency_ms,
            "congestion_bps": self.congestion_bps,
            "liquidity_capacity_minor": self.liquidity_capacity_minor,
            "throughput_headroom_bps": self.throughput_headroom_bps,
            "speed_bps": self.speed_bps,
            "estimated_cost_minor": self.estimated_cost_minor,
            "link_status": self.link_status.value,
            "telemetry_observed_at": int(
                require_aware("telemetry_observed_at", self.telemetry_observed_at).timestamp()
            ),
            "telemetry_expires_at": int(
                require_aware("telemetry_expires_at", self.telemetry_expires_at).timestamp()
            ),
        }


@dataclass(frozen=True, slots=True)
class RankedRoute:
    candidate: RouteCandidate
    score_bps: int
    component_scores: tuple[tuple[str, int], ...]
    rank: int

    def to_payload(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "score_bps": self.score_bps,
            "component_scores": dict(self.component_scores),
            "route": self.candidate.to_payload(),
        }


@dataclass(frozen=True, slots=True)
class RouteFailure:
    rtt_id: str
    route_id: str
    failure_code: str
    disposition: FailureDisposition
    recorded_at: datetime

    def to_payload(self) -> dict[str, Any]:
        return {
            "rtt_id": self.rtt_id,
            "route_id": self.route_id,
            "failure_code": self.failure_code,
            "disposition": self.disposition.value,
            "recorded_at": int(require_aware("recorded_at", self.recorded_at).timestamp()),
        }


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    plan_id: str
    utt_id: str
    ranked_routes: tuple[RankedRoute, ...]
    remaining_route_ids: tuple[str, ...]
    failures: tuple[RouteFailure, ...]
    attempts_used: int
    max_attempts: int
    routing_budget_minor: int
    routing_cost_spent_minor: int
    current_rtt_id: str | None
    previous_rtt_id: str | None
    previous_route_id: str | None
    status: PlanStatus
    successful_route_id: str | None
    version: int
    created_at: datetime
    updated_at: datetime

    @property
    def routing_budget_remaining_minor(self) -> int:
        return max(0, self.routing_budget_minor - self.routing_cost_spent_minor)


@dataclass(frozen=True, slots=True)
class RttAttemptRecord:
    rtt_id: str
    utt_id: str
    plan_id: str
    attempt_number: int
    route_id: str
    signed_rtt: SignatureEnvelope
    state: AttemptState
    failure_code: str | None
    actual_cost_minor: int | None
    created_at: datetime
    updated_at: datetime
