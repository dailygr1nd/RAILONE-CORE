"""Supervision-friendly synthetic-effect worker."""

from __future__ import annotations

from typing import Protocol
from dataclasses import dataclass
from enum import StrEnum

from .effects import SandboxEffectBroker
from .metrics import MetricsRegistry
from .models import ScheduledProviderEffect


class ProviderEffectConsumer(Protocol):
    def apply(self, effect: ScheduledProviderEffect) -> None: ...


class SandboxEffectWorker:
    """One bounded tick; the process supervisor owns repetition and shutdown."""

    def __init__(
        self, *, broker: SandboxEffectBroker, consumer: ProviderEffectConsumer,
        metrics: MetricsRegistry, worker_id: str = "sandbox-effect-worker",
        retry_delay_ticks: int = 1, lease_ticks: int = 2,
        max_attempts: int = 5,
    ) -> None:
        if not 1 <= retry_delay_ticks <= 100:
            raise ValueError("retry_delay_ticks is outside policy")
        self._broker = broker
        self._consumer = consumer
        self._metrics = metrics
        self._worker_id = worker_id
        self._retry_delay = retry_delay_ticks
        self._lease_ticks = lease_ticks
        self._max_attempts = max_attempts

    def run_once(self) -> tuple[str, ...]:
        applied: list[str] = []
        records = self._broker.claim_due(
            worker_id=self._worker_id, lease_ticks=self._lease_ticks
        )
        for record in records:
            effect = record.effect
            try:
                self._consumer.apply(effect)
            except Exception as exc:
                self._broker.reschedule(
                    effect_id=effect.effect_id, worker_id=self._worker_id,
                    delay_ticks=self._retry_delay,
                    error=f"{type(exc).__name__}: {exc}",
                    max_attempts=self._max_attempts,
                )
                self._metrics.increment(
                    "railone_sandbox_worker_failures_total",
                    provider=effect.provider_id, effect_type=effect.effect_type,
                )
                continue
            self._broker.mark_delivered(
                effect_id=effect.effect_id, worker_id=self._worker_id
            )
            applied.append(effect.effect_id)
            self._metrics.increment(
                "railone_sandbox_worker_applied_total",
                provider=effect.provider_id, effect_type=effect.effect_type,
            )
        return tuple(applied)


class SupervisorState(StrEnum):
    RUNNING = "RUNNING"
    DEGRADED = "DEGRADED"
    STOPPED = "STOPPED"


@dataclass(frozen=True, slots=True)
class SupervisorStatus:
    state: SupervisorState
    consecutive_failures: int
    cycles: int
    last_error: str | None


class WorkerSupervisor:
    """Bounded supervisor; an external process manager owns the long-running loop."""

    def __init__(self, worker: SandboxEffectWorker, *, failure_threshold: int = 3) -> None:
        if not 1 <= failure_threshold <= 100:
            raise ValueError("worker failure threshold is outside policy")
        self._worker = worker
        self._threshold = failure_threshold
        self._failures = 0
        self._cycles = 0
        self._last_error: str | None = None
        self._stopped = False

    def tick(self) -> tuple[str, ...]:
        if self._stopped:
            raise RuntimeError("worker supervisor is stopped")
        self._cycles += 1
        try:
            applied = self._worker.run_once()
        except Exception as exc:
            self._failures += 1
            self._last_error = f"{type(exc).__name__}: {exc}"[:1000]
            return ()
        self._failures = 0
        self._last_error = None
        return applied

    def stop(self) -> None:
        self._stopped = True

    def status(self) -> SupervisorStatus:
        state = (
            SupervisorState.STOPPED if self._stopped else
            SupervisorState.DEGRADED if self._failures >= self._threshold else
            SupervisorState.RUNNING
        )
        return SupervisorStatus(state, self._failures, self._cycles, self._last_error)
