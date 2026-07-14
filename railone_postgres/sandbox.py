"""Durable lease-safe store for synthetic provider effects."""

from __future__ import annotations

import hashlib

from railone_sandbox.models import (
    EffectDeliveryState, ProviderEffectRecord, ScheduledProviderEffect,
)
from railone_sandbox.store import SandboxEffectStore, _claim_policy

from .codec import json_object, json_text
from .runtime import PostgresDatabase


_COLUMNS = """effect_id, provider_id, rtt_id, external_reference, effect_type,
provider_code, due_tick, available_tick, payload, delivery_state,
delivery_attempts, lease_owner, lease_until_tick, last_error,
delivered_at_tick, version"""


class PostgresSandboxEffectStore(SandboxEffectStore):
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    def schedule(self, record: ProviderEffectRecord) -> ProviderEffectRecord:
        payload_hash = hashlib.sha256(record.effect.payload).hexdigest()
        payload = json_text(json_object(record.effect.payload.decode("utf-8")))
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO railone.sandbox_provider_effects
                   (effect_id, provider_id, rtt_id, external_reference,
                    effect_type, provider_code, due_tick, available_tick,
                    payload, payload_sha256, delivery_state, delivery_attempts,
                    lease_owner, lease_until_tick, last_error, version)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (effect_id) DO NOTHING""",
                (
                    record.effect.effect_id, record.effect.provider_id,
                    record.effect.rtt_id, record.effect.external_reference,
                    record.effect.effect_type, record.effect.provider_code,
                    record.effect.due_tick, record.available_tick, payload,
                    payload_hash, record.state.value, record.delivery_attempts,
                    record.lease_owner, record.lease_until_tick,
                    record.last_error, record.version,
                ),
            )
            cursor.execute(
                f"SELECT {_COLUMNS} FROM railone.sandbox_provider_effects WHERE effect_id=%s",
                (record.effect.effect_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("sandbox effect schedule was incomplete")
            stored = _record(row)
            if stored.effect != record.effect:
                raise RuntimeError("sandbox effect identifier collision")
            return stored

    def current_tick(self) -> int:
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT current_tick FROM railone.sandbox_runtime_clock WHERE clock_id=true"
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("sandbox runtime clock is unavailable")
            return int(row["current_tick"])

    def advance_and_claim(
        self, *, worker_id: str, ticks: int, lease_ticks: int, limit: int,
    ) -> tuple[ProviderEffectRecord, ...]:
        _claim_policy(worker_id, ticks, lease_ticks, limit)
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """UPDATE railone.sandbox_runtime_clock
                   SET current_tick=current_tick+%s, version=version+1,
                       updated_at=now()
                   WHERE clock_id=true RETURNING current_tick""",
                (ticks,),
            )
            clock = cursor.fetchone()
            if clock is None:
                raise RuntimeError("sandbox runtime clock is unavailable")
            current = int(clock["current_tick"])
            cursor.execute(
                f"""WITH eligible AS (
                       SELECT effect_id
                       FROM railone.sandbox_provider_effects
                       WHERE (delivery_state='PENDING' AND available_tick <= %s)
                          OR (delivery_state='IN_FLIGHT' AND lease_until_tick <= %s)
                       ORDER BY available_tick, effect_id
                       FOR UPDATE SKIP LOCKED LIMIT %s
                   )
                   UPDATE railone.sandbox_provider_effects AS effect
                   SET delivery_state='IN_FLIGHT',
                       delivery_attempts=effect.delivery_attempts+1,
                       lease_owner=%s, lease_until_tick=%s,
                       version=effect.version+1
                   FROM eligible
                   WHERE effect.effect_id=eligible.effect_id
                   RETURNING {_qualified_columns('effect')}""",
                (current, current, limit, worker_id, current + lease_ticks),
            )
            return tuple(_record(row) for row in cursor.fetchall())

    def mark_delivered(self, *, effect_id: str, worker_id: str) -> ProviderEffectRecord:
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT current_tick FROM railone.sandbox_runtime_clock WHERE clock_id=true"
            )
            clock = cursor.fetchone()
            if clock is None:
                raise RuntimeError("sandbox runtime clock is unavailable")
            cursor.execute(
                f"""UPDATE railone.sandbox_provider_effects
                    SET delivery_state='DELIVERED', lease_owner=NULL,
                        lease_until_tick=NULL, last_error=NULL,
                        delivered_at=now(), delivered_at_tick=%s,
                        version=version+1
                    WHERE effect_id=%s AND delivery_state='IN_FLIGHT'
                      AND lease_owner=%s
                    RETURNING {_COLUMNS}""",
                (int(clock["current_tick"]), effect_id, worker_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise PermissionError("worker does not own the sandbox effect lease")
            return _record(row)

    def reschedule(
        self, *, effect_id: str, worker_id: str, delay_ticks: int,
        error: str, max_attempts: int,
    ) -> ProviderEffectRecord:
        if not error.strip() or not 1 <= delay_ticks <= 100 or not 1 <= max_attempts <= 100:
            raise ValueError("sandbox effect retry policy is invalid")
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT current_tick FROM railone.sandbox_runtime_clock WHERE clock_id=true"
            )
            clock = cursor.fetchone()
            if clock is None:
                raise RuntimeError("sandbox runtime clock is unavailable")
            current = int(clock["current_tick"])
            cursor.execute(
                f"""UPDATE railone.sandbox_provider_effects
                    SET delivery_state=CASE WHEN delivery_attempts >= %s
                                            THEN 'DEAD_LETTER' ELSE 'PENDING' END,
                        available_tick=CASE WHEN delivery_attempts >= %s
                                            THEN available_tick ELSE %s END,
                        lease_owner=NULL, lease_until_tick=NULL,
                        last_error=%s, version=version+1
                    WHERE effect_id=%s AND delivery_state='IN_FLIGHT'
                      AND lease_owner=%s
                    RETURNING {_COLUMNS}""",
                (
                    max_attempts, max_attempts, current + delay_ticks,
                    error[:1000], effect_id, worker_id,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise PermissionError("worker does not own the sandbox effect lease")
            return _record(row)


def _qualified_columns(alias: str) -> str:
    return ", ".join(f"{alias}.{name.strip()}" for name in _COLUMNS.split(","))


def _record(row) -> ProviderEffectRecord:
    effect = ScheduledProviderEffect(
        effect_id=str(row["effect_id"]), provider_id=str(row["provider_id"]),
        rtt_id=str(row["rtt_id"]),
        external_reference=str(row["external_reference"]),
        effect_type=str(row["effect_type"]), provider_code=str(row["provider_code"]),
        due_tick=int(row["due_tick"]),
        payload=json_text(json_object(row["payload"])).encode("utf-8"),
    )
    return ProviderEffectRecord(
        effect=effect, available_tick=int(row["available_tick"]),
        state=EffectDeliveryState(row["delivery_state"]),
        delivery_attempts=int(row["delivery_attempts"]),
        lease_owner=row["lease_owner"],
        lease_until_tick=(int(row["lease_until_tick"]) if row["lease_until_tick"] is not None else None),
        last_error=row["last_error"],
        delivered_at_tick=(int(row["delivered_at_tick"]) if row["delivered_at_tick"] is not None else None),
        version=int(row["version"]),
    )
