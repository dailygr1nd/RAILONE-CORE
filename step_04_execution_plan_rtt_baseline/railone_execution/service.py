"""Execution-plan construction and RTT lifecycle services."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import datetime, timezone

from railone_contracts.models import require_minor_units, require_text
from railone_contracts.store import ContractStore
from railone_crypto.canonical_json import canonical_json_bytes
from railone_crypto.signature_service import ArtifactType, SignatureService

from .models import (
    AttemptState,
    ExecutionPlan,
    FailureDisposition,
    PlanStatus,
    RouteCandidate,
    RouteFailure,
    RttAttemptRecord,
    require_aware,
)
from .scoring import DeterministicRouteScorer
from .store import ExecutionStore


class NoEligibleRouteError(RuntimeError):
    pass


class PlanNotExecutableError(RuntimeError):
    pass


def _identifier(prefix: str, payload: object) -> str:
    digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest().upper()
    return f"{prefix}-{digest[:32]}"


class ExecutionPlanningService:
    def __init__(
        self,
        *,
        signatures: SignatureService,
        contracts: ContractStore,
        executions: ExecutionStore,
        scorer: DeterministicRouteScorer | None = None,
    ) -> None:
        self._signatures = signatures
        self._contracts = contracts
        self._executions = executions
        self._scorer = scorer or DeterministicRouteScorer()

    def build_plan(
        self,
        *,
        utt_id: str,
        candidates: tuple[RouteCandidate, ...] | list[RouteCandidate],
        at: datetime | None = None,
    ) -> ExecutionPlan:
        instant = require_aware("planning timestamp", at or datetime.now(timezone.utc))
        signed_utt = self._contracts.require_utt(require_text("utt_id", utt_id))
        verification = self._signatures.verify_artifact(
            signed_utt, expected_artifact_type=ArtifactType.UTT
        )
        if not verification.valid:
            raise PermissionError(f"UTT rejected: {verification.reason}")
        utt = signed_utt.payload
        ranked = self._scorer.rank(
            candidates,
            amount_minor=utt["amount_minor"],
            currency_from=utt["currency_from"],
            currency_to=utt["currency_to"],
            routing_budget_minor=utt["routing_budget_minor"],
            at=instant,
        )
        if not ranked:
            raise NoEligibleRouteError("no eligible route for accepted UTT")
        plan_material = {
            "utt_id": utt_id,
            "utt_payload_sha256": signed_utt.protected["payload_sha256"],
            "routing_policy_id": utt["routing_policy_id"],
            "ranked_routes": [route.to_payload() for route in ranked],
            "created_at": int(instant.timestamp()),
        }
        plan = ExecutionPlan(
            plan_id=_identifier("PLAN", plan_material),
            utt_id=utt_id,
            ranked_routes=ranked,
            remaining_route_ids=tuple(route.candidate.route_id for route in ranked),
            failures=(),
            attempts_used=0,
            max_attempts=utt["max_attempts"],
            routing_budget_minor=utt["routing_budget_minor"],
            routing_cost_spent_minor=0,
            current_rtt_id=None,
            previous_rtt_id=None,
            previous_route_id=None,
            status=PlanStatus.ACTIVE,
            successful_route_id=None,
            version=1,
            created_at=instant,
            updated_at=instant,
        )
        return self._executions.create_plan(plan)


class RttAttemptService:
    def __init__(
        self,
        *,
        signatures: SignatureService,
        contracts: ContractStore,
        executions: ExecutionStore,
        rtt_signing_key_id: str,
    ) -> None:
        self._signatures = signatures
        self._contracts = contracts
        self._executions = executions
        self._rtt_signing_key_id = rtt_signing_key_id

    def start_next(
        self, *, utt_id: str, at: datetime | None = None
    ) -> RttAttemptRecord:
        instant = require_aware("attempt timestamp", at or datetime.now(timezone.utc))
        signed_utt = self._contracts.require_utt(require_text("utt_id", utt_id))
        verification = self._signatures.verify_artifact(
            signed_utt, expected_artifact_type=ArtifactType.UTT
        )
        if not verification.valid:
            raise PermissionError(f"UTT rejected: {verification.reason}")
        plan = self._executions.require_plan_for_utt(utt_id)
        if plan.status is not PlanStatus.ACTIVE:
            raise PlanNotExecutableError(f"plan is {plan.status.value}")
        if plan.current_rtt_id is not None:
            raise PlanNotExecutableError("an RTT is already in flight")
        if plan.attempts_used >= plan.max_attempts:
            raise PlanNotExecutableError("attempt limit exhausted")

        by_id = {route.candidate.route_id: route for route in plan.ranked_routes}
        selected = next(
            (
                by_id[route_id]
                for route_id in plan.remaining_route_ids
                if by_id[route_id].candidate.estimated_cost_minor
                <= plan.routing_budget_remaining_minor
            ),
            None,
        )
        if selected is None:
            raise PlanNotExecutableError("no affordable route remains")
        attempt_number = plan.attempts_used + 1
        rtt_material = {
            "utt_id": utt_id,
            "plan_id": plan.plan_id,
            "attempt_number": attempt_number,
            "route_id": selected.candidate.route_id,
            "previous_rtt_id": plan.previous_rtt_id,
            "created_at": int(instant.timestamp()),
        }
        rtt_id = _identifier("RTT", rtt_material)
        rtt_payload = {
            "rtt_id": rtt_id,
            "utt_id": utt_id,
            "utt_payload_sha256": signed_utt.protected["payload_sha256"],
            "plan_id": plan.plan_id,
            "attempt_number": attempt_number,
            "route": selected.candidate.to_payload(),
            "route_score_bps": selected.score_bps,
            "route_component_scores": dict(selected.component_scores),
            "previous_rtt_id": plan.previous_rtt_id,
            "previous_route_id": plan.previous_route_id,
            "replay_generation": attempt_number - 1,
            "birth_state": AttemptState.CREATED.value,
            "created_at": int(instant.timestamp()),
            "custody_model": "NON_CUSTODIAL",
        }
        signed_rtt = self._signatures.sign_artifact(
            artifact_type=ArtifactType.RTT,
            payload=rtt_payload,
            key_id=self._rtt_signing_key_id,
            issued_at=instant,
        )
        attempt = RttAttemptRecord(
            rtt_id=rtt_id,
            utt_id=utt_id,
            plan_id=plan.plan_id,
            attempt_number=attempt_number,
            route_id=selected.candidate.route_id,
            signed_rtt=signed_rtt,
            state=AttemptState.CREATED,
            failure_code=None,
            actual_cost_minor=None,
            created_at=instant,
            updated_at=instant,
        )
        updated = replace(
            plan,
            remaining_route_ids=tuple(
                route_id
                for route_id in plan.remaining_route_ids
                if route_id != selected.candidate.route_id
            ),
            attempts_used=attempt_number,
            current_rtt_id=rtt_id,
            version=plan.version + 1,
            updated_at=instant,
        )
        self._executions.commit_start(
            previous_version=plan.version, plan=updated, attempt=attempt
        )
        return attempt

    def record_failure(
        self,
        *,
        rtt_id: str,
        failure_code: str,
        disposition: FailureDisposition,
        actual_cost_minor: int,
        at: datetime | None = None,
    ) -> ExecutionPlan:
        instant = require_aware("failure timestamp", at or datetime.now(timezone.utc))
        cost = require_minor_units(
            "actual_cost_minor", actual_cost_minor, allow_zero=True
        )
        code = require_text("failure_code", failure_code).upper()
        attempt = self._executions.require_attempt(require_text("rtt_id", rtt_id))
        if attempt.state is not AttemptState.CREATED:
            raise PlanNotExecutableError("RTT has already reached an operational outcome")
        plan = self._executions.require_plan(attempt.plan_id)
        failure = RouteFailure(
            rtt_id=rtt_id,
            route_id=attempt.route_id,
            failure_code=code,
            disposition=disposition,
            recorded_at=instant,
        )
        spent = plan.routing_cost_spent_minor + cost
        if disposition is FailureDisposition.RECONCILIATION_REQUIRED:
            status = PlanStatus.RECONCILIATION_REQUIRED
            current_rtt_id = rtt_id
            attempt_state = AttemptState.RECONCILIATION_REQUIRED
        elif disposition is FailureDisposition.TERMINAL:
            status = PlanStatus.FAILED
            current_rtt_id = None
            attempt_state = AttemptState.FAILED
        else:
            affordable_route_remains = any(
                route.candidate.route_id in plan.remaining_route_ids
                and route.candidate.estimated_cost_minor
                <= max(0, plan.routing_budget_minor - spent)
                for route in plan.ranked_routes
            )
            exhausted = (
                plan.attempts_used >= plan.max_attempts
                or not affordable_route_remains
            )
            status = PlanStatus.EXHAUSTED if exhausted else PlanStatus.ACTIVE
            current_rtt_id = None
            attempt_state = AttemptState.FAILED
        updated_attempt = replace(
            attempt,
            state=attempt_state,
            failure_code=code,
            actual_cost_minor=cost,
            updated_at=instant,
        )
        updated_plan = replace(
            plan,
            failures=plan.failures + (failure,),
            routing_cost_spent_minor=spent,
            current_rtt_id=current_rtt_id,
            previous_rtt_id=rtt_id,
            previous_route_id=attempt.route_id,
            status=status,
            version=plan.version + 1,
            updated_at=instant,
        )
        self._executions.commit_transition(
            previous_version=plan.version,
            plan=updated_plan,
            attempt=updated_attempt,
        )
        return updated_plan

    def record_success(
        self,
        *,
        rtt_id: str,
        actual_cost_minor: int,
        at: datetime | None = None,
    ) -> ExecutionPlan:
        instant = require_aware("success timestamp", at or datetime.now(timezone.utc))
        cost = require_minor_units(
            "actual_cost_minor", actual_cost_minor, allow_zero=True
        )
        attempt = self._executions.require_attempt(require_text("rtt_id", rtt_id))
        if attempt.state is not AttemptState.CREATED:
            raise PlanNotExecutableError("RTT has already reached an operational outcome")
        plan = self._executions.require_plan(attempt.plan_id)
        updated_attempt = replace(
            attempt,
            state=AttemptState.SUCCEEDED,
            actual_cost_minor=cost,
            updated_at=instant,
        )
        updated_plan = replace(
            plan,
            routing_cost_spent_minor=plan.routing_cost_spent_minor + cost,
            current_rtt_id=None,
            previous_rtt_id=rtt_id,
            previous_route_id=attempt.route_id,
            status=PlanStatus.FINALIZED,
            successful_route_id=attempt.route_id,
            version=plan.version + 1,
            updated_at=instant,
        )
        self._executions.commit_transition(
            previous_version=plan.version,
            plan=updated_plan,
            attempt=updated_attempt,
        )
        return updated_plan
