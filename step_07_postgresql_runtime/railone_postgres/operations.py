"""PostgreSQL provider-submission and signed-outbox repository."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

from railone_operations.models import (
    OutboxDeliveryState,
    OutboxRecord,
    ProviderSubmissionRecord,
    ProviderSubmissionState,
    RejectionDisposition,
)
from railone_operations.store import (
    ConcurrentSubmissionUpdateError,
    OperationsStore,
    SubmissionNotFoundError,
)

from .codec import envelope_from_db, json_text
from .runtime import PostgresDatabase


_SUBMISSION_COLUMNS = """submission_id, idempotency_key, request_sha256, utt_id,
rtt_id, provider_id, state, dispatch_attempts, normalized_code, external_reference,
rejection_disposition, version, created_at, updated_at"""
_OUTBOX_COLUMNS = """event_id, aggregate_type, aggregate_id, event_type,
signed_event, delivery_state, delivery_attempts, available_at, lease_owner,
lease_until, last_error, published_at, version, created_at, updated_at"""


class PostgresOperationsStore(OperationsStore):
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    def prepare(
        self, submission: ProviderSubmissionRecord, outbox: OutboxRecord
    ) -> ProviderSubmissionRecord:
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""INSERT INTO railone.provider_submissions ({_SUBMISSION_COLUMNS})
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (rtt_id) DO NOTHING
                    RETURNING {_SUBMISSION_COLUMNS}""",
                _submission_params(submission),
            )
            row = cursor.fetchone()
            if row is None:
                cursor.execute(
                    f"SELECT {_SUBMISSION_COLUMNS} FROM railone.provider_submissions WHERE rtt_id = %s",
                    (submission.rtt_id,),
                )
                existing = cursor.fetchone()
                if existing is None:
                    raise RuntimeError("provider submission conflict could not be resolved")
                stored = _submission(existing)
                if (
                    stored.idempotency_key != submission.idempotency_key
                    or stored.request_sha256 != submission.request_sha256
                ):
                    raise RuntimeError("provider submission preparation conflict")
                return stored
            self._insert_outbox(cursor, outbox)
            return _submission(row)

    def require_submission(self, rtt_id: str) -> ProviderSubmissionRecord:
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {_SUBMISSION_COLUMNS} FROM railone.provider_submissions WHERE rtt_id = %s",
                (rtt_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise SubmissionNotFoundError(f"provider submission not found: {rtt_id}")
            return _submission(row)

    def transition(
        self,
        *,
        previous_version: int,
        submission: ProviderSubmissionRecord,
        outbox: OutboxRecord,
    ) -> None:
        if submission.version != previous_version + 1:
            raise ValueError("submission version must advance exactly once")
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """UPDATE railone.provider_submissions
                   SET state=%s, dispatch_attempts=%s, normalized_code=%s,
                       external_reference=%s, rejection_disposition=%s,
                       version=%s, updated_at=%s
                   WHERE rtt_id=%s AND version=%s
                     AND state NOT IN ('ACCEPTED','REJECTED','UNKNOWN')""",
                (
                    submission.state.value, submission.dispatch_attempts,
                    submission.normalized_code, submission.external_reference,
                    submission.rejection_disposition.value
                    if submission.rejection_disposition is not None else None,
                    submission.version, submission.updated_at,
                    submission.rtt_id, previous_version,
                ),
            )
            if cursor.rowcount != 1:
                raise ConcurrentSubmissionUpdateError(
                    "provider submission changed concurrently"
                )
            self._insert_outbox(cursor, outbox)

    def pending_outbox(self, *, limit: int = 100) -> tuple[OutboxRecord, ...]:
        _limit(limit)
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""SELECT {_OUTBOX_COLUMNS} FROM railone.signed_outbox
                    WHERE delivery_state = 'PENDING'
                    ORDER BY available_at, event_id LIMIT %s""",
                (limit,),
            )
            return tuple(_outbox(row) for row in cursor.fetchall())

    def claim_outbox(
        self,
        *,
        worker_id: str,
        at: datetime,
        lease_seconds: int,
        limit: int,
    ) -> tuple[OutboxRecord, ...]:
        if not worker_id.strip():
            raise ValueError("outbox worker_id is required")
        if isinstance(lease_seconds, bool) or not 1 <= lease_seconds <= 300:
            raise ValueError("outbox lease_seconds must be between 1 and 300")
        _limit(limit)
        lease_until = at + timedelta(seconds=lease_seconds)
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""WITH claimable AS (
                    SELECT event_id FROM railone.signed_outbox
                    WHERE (delivery_state='PENDING' AND available_at <= %s)
                       OR (delivery_state='IN_FLIGHT' AND lease_until <= %s)
                    ORDER BY available_at, event_id
                    FOR UPDATE SKIP LOCKED LIMIT %s
                )
                UPDATE railone.signed_outbox AS event
                SET delivery_state='IN_FLIGHT',
                    delivery_attempts=event.delivery_attempts + 1,
                    lease_owner=%s, lease_until=%s,
                    version=event.version + 1, updated_at=%s
                FROM claimable WHERE event.event_id=claimable.event_id
                RETURNING {', '.join('event.' + name.strip() for name in _OUTBOX_COLUMNS.split(','))}""",
                (at, at, limit, worker_id, lease_until, at),
            )
            rows = cursor.fetchall()
            rows.sort(key=lambda row: (row["available_at"], row["event_id"]))
            return tuple(_outbox(row) for row in rows)

    def mark_published(
        self, *, event_id: str, worker_id: str, at: datetime
    ) -> OutboxRecord:
        return self._finish_lease(
            event_id=event_id,
            worker_id=worker_id,
            assignments="""delivery_state='PUBLISHED', lease_owner=NULL,
                           lease_until=NULL, last_error=NULL, published_at=%s""",
            assignment_params=(at,),
            at=at,
        )

    def reschedule(
        self,
        *,
        event_id: str,
        worker_id: str,
        at: datetime,
        available_at: datetime,
        error: str,
        max_attempts: int,
    ) -> OutboxRecord:
        if not error.strip():
            raise ValueError("outbox failure error is required")
        if isinstance(max_attempts, bool) or not 1 <= max_attempts <= 100:
            raise ValueError("outbox max_attempts must be between 1 and 100")
        return self._finish_lease(
            event_id=event_id,
            worker_id=worker_id,
            assignments="""delivery_state=CASE WHEN delivery_attempts >= %s
                           THEN 'DEAD_LETTER' ELSE 'PENDING' END,
                           available_at=%s, lease_owner=NULL, lease_until=NULL,
                           last_error=%s""",
            assignment_params=(max_attempts, available_at, error[:1000]),
            at=at,
        )

    def _finish_lease(
        self,
        *,
        event_id: str,
        worker_id: str,
        assignments: str,
        assignment_params: tuple[object, ...],
        at: datetime,
    ) -> OutboxRecord:
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""UPDATE railone.signed_outbox SET {assignments},
                    version=version + 1, updated_at=%s
                    WHERE event_id=%s AND delivery_state='IN_FLIGHT'
                      AND lease_owner=%s
                    RETURNING {_OUTBOX_COLUMNS}""",
                assignment_params + (at, event_id, worker_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise PermissionError("worker does not own the outbox lease")
            return _outbox(row)

    @staticmethod
    def _insert_outbox(cursor, outbox: OutboxRecord) -> None:
        cursor.execute(
            f"""INSERT INTO railone.signed_outbox
                ({_OUTBOX_COLUMNS}, event_payload_sha256)
                VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            _outbox_params(outbox) + (outbox.signed_event.protected["payload_sha256"],),
        )


def _limit(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 1000:
        raise ValueError("outbox limit must be between 1 and 1000")


def _submission_params(value: ProviderSubmissionRecord) -> tuple[object, ...]:
    return (
        value.submission_id, value.idempotency_key, value.request_sha256,
        value.utt_id, value.rtt_id, value.provider_id, value.state.value,
        value.dispatch_attempts, value.normalized_code, value.external_reference,
        value.rejection_disposition.value if value.rejection_disposition else None,
        value.version, value.created_at, value.updated_at,
    )


def _submission(row: Mapping[str, Any]) -> ProviderSubmissionRecord:
    disposition = row["rejection_disposition"]
    return ProviderSubmissionRecord(
        submission_id=str(row["submission_id"]),
        idempotency_key=str(row["idempotency_key"]),
        request_sha256=str(row["request_sha256"]), utt_id=str(row["utt_id"]),
        rtt_id=str(row["rtt_id"]), provider_id=str(row["provider_id"]),
        state=ProviderSubmissionState(row["state"]),
        dispatch_attempts=int(row["dispatch_attempts"]),
        normalized_code=row["normalized_code"],
        external_reference=row["external_reference"],
        rejection_disposition=RejectionDisposition(disposition) if disposition else None,
        version=int(row["version"]), created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _outbox_params(value: OutboxRecord) -> tuple[object, ...]:
    return (
        value.event_id, value.aggregate_type, value.aggregate_id, value.event_type,
        json_text(value.signed_event.to_dict()), value.delivery_state.value,
        value.delivery_attempts, value.available_at, value.lease_owner,
        value.lease_until, value.last_error, value.published_at, value.version,
        value.created_at, value.updated_at,
    )


def _outbox(row: Mapping[str, Any]) -> OutboxRecord:
    return OutboxRecord(
        event_id=str(row["event_id"]), aggregate_type=str(row["aggregate_type"]),
        aggregate_id=str(row["aggregate_id"]), event_type=str(row["event_type"]),
        signed_event=envelope_from_db(row["signed_event"]),
        delivery_state=OutboxDeliveryState(row["delivery_state"]),
        delivery_attempts=int(row["delivery_attempts"]),
        available_at=row["available_at"], lease_owner=row["lease_owner"],
        lease_until=row["lease_until"], last_error=row["last_error"],
        published_at=row["published_at"], version=int(row["version"]),
        created_at=row["created_at"], updated_at=row["updated_at"],
    )
