"""Lossless database codecs for immutable RailOne domain records."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from railone_crypto.signature_service import SignatureEnvelope
from railone_execution.models import (
    ExecutionPlan,
    FailureDisposition,
    LinkStatus,
    PlanStatus,
    RankedRoute,
    RouteCandidate,
    RouteFailure,
)


def json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def json_object(value: object) -> Mapping[str, Any]:
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, Mapping):
        raise ValueError("database JSON value must be an object")
    return value


def envelope_from_db(value: object) -> SignatureEnvelope:
    return SignatureEnvelope.from_dict(json_object(value))


def _instant(epoch: object) -> datetime:
    if isinstance(epoch, bool) or not isinstance(epoch, int):
        raise ValueError("stored epoch timestamp must be an integer")
    return datetime.fromtimestamp(epoch, tz=timezone.utc)


def plan_snapshot(plan: ExecutionPlan) -> dict[str, object]:
    return {
        "ranked_routes": [ranked.to_payload() for ranked in plan.ranked_routes],
        "max_attempts": plan.max_attempts,
        "routing_budget_minor": plan.routing_budget_minor,
        "created_at": int(plan.created_at.timestamp()),
    }


def plan_state(plan: ExecutionPlan) -> dict[str, object]:
    return {
        "remaining_route_ids": list(plan.remaining_route_ids),
        "failures": [failure.to_payload() for failure in plan.failures],
        "previous_route_id": plan.previous_route_id,
    }


def plan_from_row(row: Mapping[str, Any]) -> ExecutionPlan:
    snapshot = json_object(row["plan_snapshot"])
    state = json_object(row["plan_state"])
    ranked_routes = tuple(_ranked_route(item) for item in snapshot["ranked_routes"])
    failures = tuple(_failure(item) for item in state.get("failures", ()))
    return ExecutionPlan(
        plan_id=str(row["plan_id"]),
        utt_id=str(row["utt_id"]),
        ranked_routes=ranked_routes,
        remaining_route_ids=tuple(str(value) for value in state["remaining_route_ids"]),
        failures=failures,
        attempts_used=int(row["attempts_used"]),
        max_attempts=int(row["max_attempts"]),
        routing_budget_minor=int(row["routing_budget_minor"]),
        routing_cost_spent_minor=int(row["routing_cost_spent_minor"]),
        current_rtt_id=row["current_rtt_id"],
        previous_rtt_id=row["previous_rtt_id"],
        previous_route_id=state.get("previous_route_id"),
        status=PlanStatus(row["status"]),
        successful_route_id=row["successful_route_id"],
        version=int(row["version"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _ranked_route(value: object) -> RankedRoute:
    item = json_object(value)
    route = json_object(item["route"])
    components = json_object(item["component_scores"])
    candidate = RouteCandidate(
        route_id=str(route["route_id"]),
        source_institution_id=str(route["source_institution_id"]),
        destination_institution_id=str(route["destination_institution_id"]),
        rail=str(route["rail"]),
        provider=str(route["provider"]),
        adapter=str(route["adapter"]),
        currency_from=str(route["currency_from"]),
        currency_to=str(route["currency_to"]),
        min_amount_minor=int(route["min_amount_minor"]),
        max_amount_minor=int(route["max_amount_minor"]),
        latency_ms=int(route["latency_ms"]),
        congestion_bps=int(route["congestion_bps"]),
        liquidity_capacity_minor=int(route["liquidity_capacity_minor"]),
        throughput_headroom_bps=int(route["throughput_headroom_bps"]),
        speed_bps=int(route["speed_bps"]),
        estimated_cost_minor=int(route["estimated_cost_minor"]),
        link_status=LinkStatus(route["link_status"]),
        telemetry_observed_at=_instant(route["telemetry_observed_at"]),
        telemetry_expires_at=_instant(route["telemetry_expires_at"]),
    )
    return RankedRoute(
        candidate=candidate,
        score_bps=int(item["score_bps"]),
        component_scores=tuple(
            sorted((str(key), int(score)) for key, score in components.items())
        ),
        rank=int(item["rank"]),
    )


def _failure(value: object) -> RouteFailure:
    item = json_object(value)
    return RouteFailure(
        rtt_id=str(item["rtt_id"]),
        route_id=str(item["route_id"]),
        failure_code=str(item["failure_code"]),
        disposition=FailureDisposition(item["disposition"]),
        recorded_at=_instant(item["recorded_at"]),
    )
