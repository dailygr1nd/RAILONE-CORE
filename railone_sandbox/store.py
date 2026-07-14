"""Lease-safe persistence contract for deterministic provider effects."""

from __future__ import annotations

from dataclasses import replace
from threading import RLock
from typing import Protocol

from .models import EffectDeliveryState, ProviderEffectRecord


class SandboxEffectStore(Protocol):
    def schedule(self, record: ProviderEffectRecord) -> ProviderEffectRecord: ...
    def current_tick(self) -> int: ...
    def advance_and_claim(
        self, *, worker_id: str, ticks: int, lease_ticks: int, limit: int,
    ) -> tuple[ProviderEffectRecord, ...]: ...
    def mark_delivered(self, *, effect_id: str, worker_id: str) -> ProviderEffectRecord: ...
    def reschedule(
        self, *, effect_id: str, worker_id: str, delay_ticks: int,
        error: str, max_attempts: int,
    ) -> ProviderEffectRecord: ...


class InMemorySandboxEffectStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._tick = 0
        self._records: dict[str, ProviderEffectRecord] = {}

    def schedule(self, record: ProviderEffectRecord) -> ProviderEffectRecord:
        with self._lock:
            existing = self._records.get(record.effect.effect_id)
            if existing is not None:
                if existing.effect != record.effect:
                    raise RuntimeError("sandbox effect identifier collision")
                return existing
            self._records[record.effect.effect_id] = record
            return record

    def current_tick(self) -> int:
        with self._lock:
            return self._tick

    def advance_and_claim(
        self, *, worker_id: str, ticks: int, lease_ticks: int, limit: int,
    ) -> tuple[ProviderEffectRecord, ...]:
        _claim_policy(worker_id, ticks, lease_ticks, limit)
        with self._lock:
            self._tick += ticks
            eligible = [
                record for record in self._records.values()
                if (
                    record.state is EffectDeliveryState.PENDING
                    and record.available_tick <= self._tick
                ) or (
                    record.state is EffectDeliveryState.IN_FLIGHT
                    and record.lease_until_tick is not None
                    and record.lease_until_tick <= self._tick
                )
            ]
            eligible.sort(key=lambda row: (row.available_tick, row.effect.effect_id))
            claimed = []
            for record in eligible[:limit]:
                updated = replace(
                    record, state=EffectDeliveryState.IN_FLIGHT,
                    delivery_attempts=record.delivery_attempts + 1,
                    lease_owner=worker_id,
                    lease_until_tick=self._tick + lease_ticks,
                    version=record.version + 1,
                )
                self._records[record.effect.effect_id] = updated
                claimed.append(updated)
            return tuple(claimed)

    def mark_delivered(self, *, effect_id: str, worker_id: str) -> ProviderEffectRecord:
        with self._lock:
            record = self._require_owned(effect_id, worker_id)
            updated = replace(
                record, state=EffectDeliveryState.DELIVERED,
                lease_owner=None, lease_until_tick=None,
                last_error=None, delivered_at_tick=self._tick,
                version=record.version + 1,
            )
            self._records[effect_id] = updated
            return updated

    def reschedule(
        self, *, effect_id: str, worker_id: str, delay_ticks: int,
        error: str, max_attempts: int,
    ) -> ProviderEffectRecord:
        if not error.strip() or not 1 <= delay_ticks <= 100 or not 1 <= max_attempts <= 100:
            raise ValueError("sandbox effect retry policy is invalid")
        with self._lock:
            record = self._require_owned(effect_id, worker_id)
            terminal = record.delivery_attempts >= max_attempts
            updated = replace(
                record,
                available_tick=(record.available_tick if terminal else self._tick + delay_ticks),
                state=(EffectDeliveryState.DEAD_LETTER if terminal else EffectDeliveryState.PENDING),
                lease_owner=None, lease_until_tick=None, last_error=error[:1000],
                version=record.version + 1,
            )
            self._records[effect_id] = updated
            return updated

    def _require_owned(self, effect_id: str, worker_id: str) -> ProviderEffectRecord:
        try:
            record = self._records[effect_id]
        except KeyError as exc:
            raise LookupError("sandbox effect was not found") from exc
        if record.state is not EffectDeliveryState.IN_FLIGHT or record.lease_owner != worker_id:
            raise PermissionError("worker does not own the sandbox effect lease")
        return record


def _claim_policy(worker_id: str, ticks: int, lease_ticks: int, limit: int) -> None:
    if not worker_id.strip():
        raise ValueError("sandbox worker_id is required")
    for name, value, minimum, maximum in (
        ("ticks", ticks, 1, 1000), ("lease_ticks", lease_ticks, 1, 1000),
        ("limit", limit, 1, 1000),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            raise ValueError(f"{name} is outside policy")
