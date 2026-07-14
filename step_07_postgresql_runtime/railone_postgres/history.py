"""PostgreSQL privacy-limited UTT transaction-history projection store."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from railone_history.models import (
    AccessOutcome,
    SubjectKind,
    TransactionAccessAudit,
    TransactionRole,
    TransactionSubjectLink,
    UttTransactionProjection,
)
from railone_history.store import (
    TransactionHistoryStore,
    TransactionProjectionNotFoundError,
)

from .runtime import PostgresDatabase


_PROJECTION_COLUMNS = """utt_id, utt_payload_sha256, quote_id, purpose,
context_type, amount_minor, currency_from, receive_amount_minor, currency_to,
commercial_state, accepted_at, indexed_at"""


class PostgresTransactionHistoryStore(TransactionHistoryStore):
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    def commit(
        self,
        projection: UttTransactionProjection,
        links: tuple[TransactionSubjectLink, ...],
    ) -> UttTransactionProjection:
        if not links:
            raise ValueError("UTT transaction projection requires at least one subject")
        if any(link.utt_id != projection.utt_id for link in links):
            raise ValueError("transaction link UTT does not match projection")
        unique = {(link.subject_kind, link.subject_id) for link in links}
        if len(unique) != len(links):
            raise ValueError("transaction subject links must be aggregated")
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""INSERT INTO railone.utt_transaction_projections ({_PROJECTION_COLUMNS})
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (utt_id) DO NOTHING
                    RETURNING {_PROJECTION_COLUMNS}""",
                _projection_params(projection),
            )
            row = cursor.fetchone()
            if row is None:
                cursor.execute(
                    f"SELECT {_PROJECTION_COLUMNS} FROM railone.utt_transaction_projections WHERE utt_id=%s",
                    (projection.utt_id,),
                )
                existing = cursor.fetchone()
                if existing is None or existing["utt_payload_sha256"] != projection.utt_payload_sha256:
                    raise RuntimeError("UTT transaction projection conflict")
                return _projection(existing)
            for link in links:
                cursor.execute(
                    """INSERT INTO railone.utt_subject_links
                       (utt_id, subject_kind, subject_id, roles, linked_at)
                       VALUES (%s,%s,%s,%s,%s)""",
                    (
                        link.utt_id, link.subject_kind.value, link.subject_id,
                        [role.value for role in link.roles], link.linked_at,
                    ),
                )
            return _projection(row)

    def require_projection(self, utt_id: str) -> UttTransactionProjection:
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {_PROJECTION_COLUMNS} FROM railone.utt_transaction_projections WHERE utt_id=%s",
                (utt_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise TransactionProjectionNotFoundError(
                    f"transaction projection not found: {utt_id}"
                )
            return _projection(row)

    def links_for_utt(self, utt_id: str) -> tuple[TransactionSubjectLink, ...]:
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT utt_id, subject_kind, subject_id, roles, linked_at
                   FROM railone.utt_subject_links WHERE utt_id=%s
                   ORDER BY subject_kind, subject_id""",
                (utt_id,),
            )
            rows = cursor.fetchall()
            if not rows:
                raise TransactionProjectionNotFoundError(
                    f"transaction projection not found: {utt_id}"
                )
            return tuple(_link(row) for row in rows)

    def list_for_subject(
        self, subject_kind: SubjectKind, subject_id: str
    ) -> tuple[tuple[UttTransactionProjection, TransactionSubjectLink], ...]:
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""SELECT {', '.join('p.' + name.strip() for name in _PROJECTION_COLUMNS.split(','))},
                           l.subject_kind, l.subject_id, l.roles, l.linked_at
                    FROM railone.utt_subject_links l
                    JOIN railone.utt_transaction_projections p ON p.utt_id=l.utt_id
                    WHERE l.subject_kind=%s AND l.subject_id=%s
                    ORDER BY p.accepted_at DESC, p.utt_id DESC""",
                (subject_kind.value, subject_id),
            )
            return tuple((_projection(row), _link(row)) for row in cursor.fetchall())

    def append_audit(self, audit: TransactionAccessAudit) -> None:
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO railone.transaction_access_audit
                   (audit_id, principal_id, target_kind, target_id, outcome,
                    access_reason, occurred_at) VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (
                    audit.audit_id, audit.principal_id, audit.target_kind,
                    audit.target_id, audit.outcome.value, audit.access_reason,
                    audit.occurred_at,
                ),
            )


def _projection_params(value: UttTransactionProjection) -> tuple[object, ...]:
    return (
        value.utt_id, value.utt_payload_sha256, value.quote_id, value.purpose,
        value.context_type, value.amount_minor, value.currency_from,
        value.receive_amount_minor, value.currency_to, value.commercial_state,
        value.accepted_at, value.indexed_at,
    )


def _projection(row: Mapping[str, Any]) -> UttTransactionProjection:
    return UttTransactionProjection(
        utt_id=str(row["utt_id"]), utt_payload_sha256=str(row["utt_payload_sha256"]),
        quote_id=str(row["quote_id"]), purpose=str(row["purpose"]),
        context_type=str(row["context_type"]), amount_minor=int(row["amount_minor"]),
        currency_from=str(row["currency_from"]),
        receive_amount_minor=int(row["receive_amount_minor"]),
        currency_to=str(row["currency_to"]),
        commercial_state=str(row["commercial_state"]),
        accepted_at=row["accepted_at"], indexed_at=row["indexed_at"],
    )


def _link(row: Mapping[str, Any]) -> TransactionSubjectLink:
    return TransactionSubjectLink(
        utt_id=str(row["utt_id"]), subject_kind=SubjectKind(row["subject_kind"]),
        subject_id=str(row["subject_id"]),
        roles=tuple(TransactionRole(role) for role in row["roles"]),
        linked_at=row["linked_at"],
    )
