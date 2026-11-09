"""Immutable, replay-verifiable birth record for the initial route decision.

This is content-addressed integrity evidence, NOT a signature or permission to
send funds. Existing route state, UTT authority and RTT safety gates are unchanged.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from railone_crypto.canonical_json import canonical_json_bytes
from .models import ExecutionPlan, LinkStatus, RouteCandidate, require_aware
from .scoring import DeterministicRouteScorer, RouteScoreWeights

SCHEMA_VERSION = 1
SCORING_ALGORITHM = "R1-INTEGER-WEIGHTED-BPS-V1"
_HASH_DOMAIN = b"RAILONE:ROUTE-DECISION:V1\x00"
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_WEIGHT_FIELDS = ("latency", "congestion", "liquidity", "throughput", "speed", "cost", "link")


def _micros(value: datetime) -> int:
    delta = require_aware("decision timestamp", value) - _EPOCH
    return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds


def _from_micros(value: object) -> datetime:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("decision timestamp must be integer microseconds")
    return _EPOCH + timedelta(microseconds=value)


def _candidate_snapshot(candidate: RouteCandidate) -> dict[str, object]:
    return {
        "route": candidate.to_payload(),
        "telemetry_observed_at_us": _micros(candidate.telemetry_observed_at),
        "telemetry_expires_at_us": _micros(candidate.telemetry_expires_at),
    }


def _candidate_from_snapshot(snapshot: dict[str, Any]) -> RouteCandidate:
    route = snapshot["route"]
    observed = _from_micros(snapshot["telemetry_observed_at_us"])
    expires = _from_micros(snapshot["telemetry_expires_at_us"])
    # Snapshot retains full microsecond precision even though the historical
    # RouteCandidate.to_payload() carries timestamps at second precision.
    if int(observed.timestamp()) != route["telemetry_observed_at"]:
        raise ValueError("route telemetry observation timestamp mismatch")
    if int(expires.timestamp()) != route["telemetry_expires_at"]:
        raise ValueError("route telemetry expiry timestamp mismatch")
    candidate = RouteCandidate(
        route_id=route["route_id"],
        source_institution_id=route["source_institution_id"],
        destination_institution_id=route["destination_institution_id"],
        rail=route["rail"], provider=route["provider"], adapter=route["adapter"],
        currency_from=route["currency_from"], currency_to=route["currency_to"],
        min_amount_minor=route["min_amount_minor"], max_amount_minor=route["max_amount_minor"],
        latency_ms=route["latency_ms"], congestion_bps=route["congestion_bps"],
        liquidity_capacity_minor=route["liquidity_capacity_minor"],
        throughput_headroom_bps=route["throughput_headroom_bps"],
        speed_bps=route["speed_bps"], estimated_cost_minor=route["estimated_cost_minor"],
        link_status=LinkStatus(route["link_status"]),
        telemetry_observed_at=observed, telemetry_expires_at=expires,
    )
    if candidate.to_payload() != route:
        raise ValueError("route candidate is not canonically representable")
    return candidate


def _weights_payload(weights: RouteScoreWeights) -> dict[str, int]:
    return {name: getattr(weights, name) for name in _WEIGHT_FIELDS}


def _digest(canonical: bytes) -> str:
    return hashlib.sha256(_HASH_DOMAIN + canonical).hexdigest()


@dataclass(frozen=True, slots=True)
class RouteDecisionRecord:
    """Persistent, content-addressed, reproducible original planning decision.

    `canonical_body` is a string rather than a mutable nested dict so callers
    cannot mutate signed/hash-checked evidence through a Python reference.
    `payload()` always returns an independent object.
    """

    decision_id: str
    plan_id: str
    utt_id: str
    decision_sha256: str
    canonical_body: str

    @property
    def payload(self) -> dict[str, Any]:
        return json.loads(self.canonical_body)

    @classmethod
    def create(
        cls, *, plan: ExecutionPlan, utt_payload_sha256: str,
        routing_policy_id: str, scorer: DeterministicRouteScorer,
        candidates: tuple[RouteCandidate, ...] | list[RouteCandidate],
        amount_minor: int, currency_from: str, currency_to: str,
        routing_budget_minor: int, source_institution_id: str,
        destination_institution_id: str, at: datetime,
    ) -> "RouteDecisionRecord":
        instant = require_aware("decision timestamp", at)
        candidates = tuple(candidates)
        route_ids = [route.route_id for route in candidates]
        if len(route_ids) != len(set(route_ids)):
            raise ValueError("duplicate route identifier in decision candidates")
        request: dict[str, object] = {
            "amount_minor": amount_minor,
            "currency_from": currency_from.upper(), "currency_to": currency_to.upper(),
            "routing_budget_minor": routing_budget_minor,
            "source_institution_id": source_institution_id,
            "destination_institution_id": destination_institution_id,
            "decided_at_us": _micros(instant),
        }
        exclusion_rows = []
        for candidate in sorted(candidates, key=lambda candidate: candidate.route_id):
            reasons = scorer.rejection_reasons(
                candidate, amount_minor=amount_minor, currency_from=currency_from,
                currency_to=currency_to, routing_budget_minor=routing_budget_minor,
                source_institution_id=source_institution_id,
                destination_institution_id=destination_institution_id, at=instant,
            )
            if reasons:
                exclusion_rows.append({"route_id": candidate.route_id, "reasons": list(reasons)})
        body = {
            "schema_version": SCHEMA_VERSION,
            "plan_id": plan.plan_id,
            "utt_id": plan.utt_id,
            "utt_payload_sha256": utt_payload_sha256,
            "routing_policy_id": routing_policy_id,
            "scoring_algorithm": SCORING_ALGORITHM,
            "weights_bps": _weights_payload(scorer.weights),
            "request": request,
            "candidate_snapshots": [
                _candidate_snapshot(candidate)
                for candidate in sorted(candidates, key=lambda candidate: candidate.route_id)
            ],
            "excluded_routes": exclusion_rows,
            "ranked_routes": [route.to_payload() for route in plan.ranked_routes],
            "selected_route_id": plan.ranked_routes[0].candidate.route_id if plan.ranked_routes else None,
        }
        canonical = canonical_json_bytes(body)
        digest = _digest(canonical)
        record = cls(
            decision_id="RDEC-" + digest[:32].upper(),
            plan_id=plan.plan_id, utt_id=plan.utt_id,
            decision_sha256=digest, canonical_body=canonical.decode("utf-8"),
        )
        record.verify(plan=plan, expected_utt_payload_sha256=utt_payload_sha256)
        return record

    def verify(
        self, *, plan: ExecutionPlan | None = None,
        expected_utt_payload_sha256: str | None = None,
    ) -> None:
        """Recompute stored decision from its immutable inputs; raise on divergence."""
        try:
            body = self.payload
            canonical = canonical_json_bytes(body)
            if canonical.decode("utf-8") != self.canonical_body:
                raise ValueError("route decision body is not canonical JSON")
            digest = _digest(canonical)
            if digest != self.decision_sha256 or self.decision_id != "RDEC-" + digest[:32].upper():
                raise ValueError("route decision content digest or identifier does not match")
            if body["schema_version"] != SCHEMA_VERSION or body["scoring_algorithm"] != SCORING_ALGORITHM:
                raise ValueError("unsupported route decision schema/scorer version")
            if body["plan_id"] != self.plan_id or body["utt_id"] != self.utt_id:
                raise ValueError("route decision lineage mismatch")
            if (expected_utt_payload_sha256 is not None and
                    body["utt_payload_sha256"] != expected_utt_payload_sha256):
                raise ValueError("route decision does not match verified UTT digest")
            weights = RouteScoreWeights(**body["weights_bps"])
            scorer = DeterministicRouteScorer(weights)
            request = body["request"]
            instant = _from_micros(request["decided_at_us"])
            inputs = {
                "amount_minor": request["amount_minor"],
                "currency_from": request["currency_from"],
                "currency_to": request["currency_to"],
                "routing_budget_minor": request["routing_budget_minor"],
                "source_institution_id": request["source_institution_id"],
                "destination_institution_id": request["destination_institution_id"],
                "at": instant,
            }
            candidates = tuple(_candidate_from_snapshot(item) for item in body["candidate_snapshots"])
            ids = [candidate.route_id for candidate in candidates]
            if ids != sorted(ids) or len(ids) != len(set(ids)):
                raise ValueError("route candidate order or identity is invalid")
            exclusions = [
                {"route_id": candidate.route_id, "reasons": list(reasons)}
                for candidate in candidates
                if (reasons := scorer.rejection_reasons(candidate, **inputs))
            ]
            ranked = scorer.rank(candidates, **inputs)
            ranked_payload = [route.to_payload() for route in ranked]
            if exclusions != body["excluded_routes"]:
                raise ValueError("route exclusion evidence is inconsistent")
            if ranked_payload != body["ranked_routes"]:
                raise ValueError("route ranking evidence is inconsistent")
            selected = ranked[0].candidate.route_id if ranked else None
            if selected != body["selected_route_id"]:
                raise ValueError("selected route does not match highest ranked candidate")
            if not ranked:
                raise ValueError("no eligible route was recorded")
            if plan is not None:
                if plan.plan_id != self.plan_id or plan.utt_id != self.utt_id:
                    raise ValueError("route decision belongs to another plan")
                if [route.to_payload() for route in plan.ranked_routes] != ranked_payload:
                    raise ValueError("route decision does not match persisted plan ranking")
                if plan.routing_budget_minor != request["routing_budget_minor"]:
                    raise ValueError("route decision routing budget does not match plan")
        except (TypeError, KeyError, IndexError, AttributeError) as exc:
            raise ValueError("invalid route decision record shape") from exc
