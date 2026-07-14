"""Persistence boundary for execution plans and immutable RTT birth artifacts."""

from __future__ import annotations

from threading import RLock
from typing import Protocol

from railone_contracts.store import ContractStore

from .models import ExecutionPlan, RttAttemptRecord


class ExecutionPlanNotFoundError(LookupError):
    pass


class RttNotFoundError(LookupError):
    pass


class ConcurrentPlanUpdateError(RuntimeError):
    pass


class ExecutionPlanConflictError(RuntimeError):
    pass


class ExecutionStore(Protocol):
    def create_plan(self, plan: ExecutionPlan) -> ExecutionPlan: ...
    def require_plan_for_utt(self, utt_id: str) -> ExecutionPlan: ...
    def require_plan(self, plan_id: str) -> ExecutionPlan: ...
    def require_attempt(self, rtt_id: str) -> RttAttemptRecord: ...
    def commit_start(
        self, *, previous_version: int, plan: ExecutionPlan, attempt: RttAttemptRecord
    ) -> None: ...
    def commit_transition(
        self, *, previous_version: int, plan: ExecutionPlan, attempt: RttAttemptRecord
    ) -> None: ...


class InMemoryExecutionStore:
    """Test adapter mirroring database FK, unique, and CAS transaction rules."""

    def __init__(self, contracts: ContractStore) -> None:
        self._contracts = contracts
        self._lock = RLock()
        self._plans: dict[str, ExecutionPlan] = {}
        self._plan_by_utt: dict[str, str] = {}
        self._attempts: dict[str, RttAttemptRecord] = {}

    def create_plan(self, plan: ExecutionPlan) -> ExecutionPlan:
        self._contracts.require_utt(plan.utt_id)
        with self._lock:
            existing_id = self._plan_by_utt.get(plan.utt_id)
            if existing_id is not None:
                if existing_id != plan.plan_id:
                    raise ExecutionPlanConflictError(
                        "UTT already has a different execution plan"
                    )
                return self._plans[existing_id]
            if plan.plan_id in self._plans:
                raise RuntimeError("execution plan identifier collision")
            self._plans[plan.plan_id] = plan
            self._plan_by_utt[plan.utt_id] = plan.plan_id
            return plan

    def require_plan_for_utt(self, utt_id: str) -> ExecutionPlan:
        with self._lock:
            plan_id = self._plan_by_utt.get(utt_id)
            if plan_id is None:
                raise ExecutionPlanNotFoundError(f"execution plan not found for {utt_id}")
            return self._plans[plan_id]

    def require_plan(self, plan_id: str) -> ExecutionPlan:
        with self._lock:
            plan = self._plans.get(plan_id)
            if plan is None:
                raise ExecutionPlanNotFoundError(f"execution plan not found: {plan_id}")
            return plan

    def require_attempt(self, rtt_id: str) -> RttAttemptRecord:
        with self._lock:
            attempt = self._attempts.get(rtt_id)
            if attempt is None:
                raise RttNotFoundError(f"RTT attempt not found: {rtt_id}")
            return attempt

    def commit_start(
        self, *, previous_version: int, plan: ExecutionPlan, attempt: RttAttemptRecord
    ) -> None:
        self._contracts.require_utt(plan.utt_id)
        with self._lock:
            current = self._plans.get(plan.plan_id)
            if current is None or current.version != previous_version:
                raise ConcurrentPlanUpdateError("execution plan changed concurrently")
            if current.current_rtt_id is not None:
                raise RuntimeError("an RTT is already in flight")
            if attempt.rtt_id in self._attempts:
                raise RuntimeError("RTT identifier collision")
            if attempt.utt_id != plan.utt_id or attempt.plan_id != plan.plan_id:
                raise ValueError("RTT lineage does not match execution plan")
            self._attempts[attempt.rtt_id] = attempt
            self._plans[plan.plan_id] = plan

    def commit_transition(
        self, *, previous_version: int, plan: ExecutionPlan, attempt: RttAttemptRecord
    ) -> None:
        with self._lock:
            current = self._plans.get(plan.plan_id)
            prior_attempt = self._attempts.get(attempt.rtt_id)
            if current is None or current.version != previous_version:
                raise ConcurrentPlanUpdateError("execution plan changed concurrently")
            if prior_attempt is None:
                raise RttNotFoundError(f"RTT attempt not found: {attempt.rtt_id}")
            if current.current_rtt_id != attempt.rtt_id:
                raise RuntimeError("RTT is not the current in-flight attempt")
            self._attempts[attempt.rtt_id] = attempt
            self._plans[plan.plan_id] = plan
