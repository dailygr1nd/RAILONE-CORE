"""PostgreSQL ExecutionPlan and RTT repository."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from railone_crypto.signature_service import SignatureEnvelope
from railone_execution.models import AttemptState, ExecutionPlan, RttAttemptRecord
from railone_execution.store import (
    ConcurrentPlanUpdateError,
    ExecutionPlanConflictError,
    ExecutionPlanNotFoundError,
    ExecutionStore,
    RttNotFoundError,
)

from .codec import envelope_from_db, json_text, plan_from_row, plan_snapshot, plan_state
from .runtime import PostgresDatabase


_PLAN_COLUMNS = """plan_id, utt_id, plan_snapshot, plan_state, status,
attempts_used, max_attempts, routing_budget_minor, routing_cost_spent_minor,
current_rtt_id, previous_rtt_id, successful_route_id, version, created_at, updated_at"""


class PostgresExecutionStore(ExecutionStore):
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    def create_plan(self, plan: ExecutionPlan) -> ExecutionPlan:
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""INSERT INTO railone.execution_plans ({_PLAN_COLUMNS})
                VALUES (%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (utt_id) DO NOTHING
                RETURNING {_PLAN_COLUMNS}""",
                _plan_params(plan),
            )
            row = cursor.fetchone()
            if row is not None:
                return plan_from_row(row)
            cursor.execute(
                f"SELECT {_PLAN_COLUMNS} FROM railone.execution_plans WHERE utt_id = %s",
                (plan.utt_id,),
            )
            existing = cursor.fetchone()
            if existing is None or existing["plan_id"] != plan.plan_id:
                raise ExecutionPlanConflictError("UTT already has a different execution plan")
            return plan_from_row(existing)

    def require_plan_for_utt(self, utt_id: str) -> ExecutionPlan:
        return self._require_plan("utt_id", utt_id)

    def require_plan(self, plan_id: str) -> ExecutionPlan:
        return self._require_plan("plan_id", plan_id)

    def require_attempt(self, rtt_id: str) -> RttAttemptRecord:
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT rtt_id, utt_id, plan_id, attempt_number, route_id,
                          signed_rtt, state, failure_code, actual_cost_minor,
                          created_at, updated_at
                   FROM railone.rtt_attempts WHERE rtt_id = %s""",
                (rtt_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise RttNotFoundError(f"RTT attempt not found: {rtt_id}")
            return _attempt(row)

    def commit_start(
        self, *, previous_version: int, plan: ExecutionPlan, attempt: RttAttemptRecord
    ) -> None:
        if plan.version != previous_version + 1:
            raise ValueError("execution plan version must advance exactly once")
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO railone.rtt_attempts
                   (rtt_id, utt_id, plan_id, attempt_number, route_id,
                    rtt_payload_sha256, signed_rtt, state, failure_code,
                    actual_cost_minor, version, created_at, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,1,%s,%s)""",
                _attempt_params(attempt),
            )
            self._update_plan(cursor, previous_version, plan, require_no_current=True)

    def commit_transition(
        self, *, previous_version: int, plan: ExecutionPlan, attempt: RttAttemptRecord
    ) -> None:
        if plan.version != previous_version + 1:
            raise ValueError("execution plan version must advance exactly once")
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """UPDATE railone.rtt_attempts
                   SET state = %s, failure_code = %s, actual_cost_minor = %s,
                       version = version + 1, updated_at = %s
                   WHERE rtt_id = %s AND plan_id = %s AND state = 'CREATED'""",
                (
                    attempt.state.value, attempt.failure_code, attempt.actual_cost_minor,
                    attempt.updated_at, attempt.rtt_id, attempt.plan_id,
                ),
            )
            if cursor.rowcount != 1:
                raise RttNotFoundError("RTT is missing or already has an outcome")
            self._update_plan(cursor, previous_version, plan, current_rtt=attempt.rtt_id)

    def _require_plan(self, column: str, value: str) -> ExecutionPlan:
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {_PLAN_COLUMNS} FROM railone.execution_plans WHERE {column} = %s",
                (value,),
            )
            row = cursor.fetchone()
            if row is None:
                raise ExecutionPlanNotFoundError(f"execution plan not found: {value}")
            return plan_from_row(row)

    @staticmethod
    def _update_plan(
        cursor,
        previous_version: int,
        plan: ExecutionPlan,
        *,
        require_no_current: bool = False,
        current_rtt: str | None = None,
    ) -> None:
        predicate = " AND current_rtt_id IS NULL" if require_no_current else ""
        params: tuple[object, ...] = _plan_update_params(plan) + (
            plan.plan_id,
            previous_version,
        )
        if current_rtt is not None:
            predicate += " AND current_rtt_id = %s"
            params += (current_rtt,)
        cursor.execute(
            f"""UPDATE railone.execution_plans
                SET plan_state = %s::jsonb, status = %s, attempts_used = %s,
                    routing_cost_spent_minor = %s, current_rtt_id = %s,
                    previous_rtt_id = %s, successful_route_id = %s,
                    version = %s, updated_at = %s
                WHERE plan_id = %s AND version = %s{predicate}""",
            params,
        )
        if cursor.rowcount != 1:
            raise ConcurrentPlanUpdateError("execution plan changed concurrently")


def _plan_params(plan: ExecutionPlan) -> tuple[object, ...]:
    return (
        plan.plan_id, plan.utt_id, json_text(plan_snapshot(plan)),
        json_text(plan_state(plan)), plan.status.value, plan.attempts_used,
        plan.max_attempts, plan.routing_budget_minor, plan.routing_cost_spent_minor,
        plan.current_rtt_id, plan.previous_rtt_id, plan.successful_route_id,
        plan.version, plan.created_at, plan.updated_at,
    )


def _plan_update_params(plan: ExecutionPlan) -> tuple[object, ...]:
    return (
        json_text(plan_state(plan)), plan.status.value, plan.attempts_used,
        plan.routing_cost_spent_minor, plan.current_rtt_id, plan.previous_rtt_id,
        plan.successful_route_id, plan.version, plan.updated_at,
    )


def _attempt_params(attempt: RttAttemptRecord) -> tuple[object, ...]:
    return (
        attempt.rtt_id, attempt.utt_id, attempt.plan_id, attempt.attempt_number,
        attempt.route_id, attempt.signed_rtt.protected["payload_sha256"],
        json_text(attempt.signed_rtt.to_dict()), attempt.state.value,
        attempt.failure_code, attempt.actual_cost_minor,
        attempt.created_at, attempt.updated_at,
    )


def _attempt(row: Mapping[str, Any]) -> RttAttemptRecord:
    return RttAttemptRecord(
        rtt_id=str(row["rtt_id"]), utt_id=str(row["utt_id"]),
        plan_id=str(row["plan_id"]), attempt_number=int(row["attempt_number"]),
        route_id=str(row["route_id"]), signed_rtt=envelope_from_db(row["signed_rtt"]),
        state=AttemptState(row["state"]), failure_code=row["failure_code"],
        actual_cost_minor=row["actual_cost_minor"], created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
