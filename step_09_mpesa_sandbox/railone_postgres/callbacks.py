"""PostgreSQL sanitized provider callback inbox."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from railone_callbacks import (
    CallbackInboxRecord,
    CallbackPayloadConflictError,
    CallbackState,
)
from railone_callbacks.store import CallbackInboxStore

from .codec import json_object, json_text
from .runtime import PostgresDatabase


class PostgresCallbackInboxStore(CallbackInboxStore):
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    def ingest(
        self,
        *,
        provider_id: str,
        provider_event_id: str,
        payload_sha256: str,
        normalized_payload: Mapping[str, object],
        signature_valid: bool,
        received_at: datetime,
    ) -> tuple[CallbackInboxRecord, bool]:
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO railone.provider_callback_inbox
                   (provider_id, provider_event_id, payload_sha256, raw_payload,
                    signature_valid, received_at, applied_at)
                   VALUES (%s,%s,%s,%s::jsonb,%s,%s,NULL)
                   ON CONFLICT (provider_id, provider_event_id) DO NOTHING
                   RETURNING provider_id, provider_event_id, payload_sha256,
                             raw_payload, signature_valid, received_at, applied_at""",
                (
                    provider_id, provider_event_id, payload_sha256,
                    json_text(dict(normalized_payload)), signature_valid, received_at,
                ),
            )
            row = cursor.fetchone()
            if row is not None:
                return _record(row), False
            cursor.execute(
                """SELECT provider_id, provider_event_id, payload_sha256,
                          raw_payload, signature_valid, received_at, applied_at
                   FROM railone.provider_callback_inbox
                   WHERE provider_id=%s AND provider_event_id=%s""",
                (provider_id, provider_event_id),
            )
            existing = cursor.fetchone()
            if existing is None or existing["payload_sha256"] != payload_sha256:
                raise CallbackPayloadConflictError(
                    "provider callback identifier was reused with different material"
                )
            return _record(existing), True

    def mark_applied(
        self, *, provider_id: str, provider_event_id: str, at: datetime
    ) -> CallbackInboxRecord:
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """UPDATE railone.provider_callback_inbox SET applied_at=%s
                   WHERE provider_id=%s AND provider_event_id=%s AND applied_at IS NULL
                   RETURNING provider_id, provider_event_id, payload_sha256,
                             raw_payload, signature_valid, received_at, applied_at""",
                (at, provider_id, provider_event_id),
            )
            row = cursor.fetchone()
            if row is not None:
                return _record(row)
            cursor.execute(
                """SELECT provider_id, provider_event_id, payload_sha256,
                          raw_payload, signature_valid, received_at, applied_at
                   FROM railone.provider_callback_inbox
                   WHERE provider_id=%s AND provider_event_id=%s""",
                (provider_id, provider_event_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise LookupError("provider callback not found")
            return _record(row)


def _record(row) -> CallbackInboxRecord:
    return CallbackInboxRecord(
        provider_id=str(row["provider_id"]),
        provider_event_id=str(row["provider_event_id"]),
        payload_sha256=str(row["payload_sha256"]),
        normalized_payload=json_object(row["raw_payload"]),
        signature_valid=bool(row["signature_valid"]),
        state=CallbackState.APPLIED if row["applied_at"] else CallbackState.RECEIVED,
        received_at=row["received_at"], applied_at=row["applied_at"],
    )
