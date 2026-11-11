"""PostgreSQL append-only, redacted institutional admission audit sink."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from railone_security.incident_audit import rejection_code
from .runtime import PostgresDatabase


class PostgresSecurityAuditStore:
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    def record_rejection(
        self, *, event_type: str, operation: str, correlation_ref: str,
        error: Exception, at: datetime,
    ) -> None:
        if event_type not in {"INSTITUTION_DISPATCH_REJECTED", "BILATERAL_AUTH_REJECTED"}:
            raise ValueError("invalid security event type")
        if operation not in {"ACCEPT", "PLAN", "RTT_CREATE", "PREFLIGHT", "ADMIT"}:
            raise ValueError("invalid security operation")
        # Correlation references are safe bounded IDs. Never persist arbitrary
        # exception messages or attacker-supplied payload content.
        safe_ref = correlation_ref if (isinstance(correlation_ref, str)
                  and 1 <= len(correlation_ref) <= 128
                  and all(c.isascii() and (c.isalnum() or c in '-_:') for c in correlation_ref)) else "INVALID-REFERENCE"
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO railone.institution_security_audit
                   (event_id, occurred_at, event_type, operation,
                    correlation_ref, reason_code)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (uuid4(), at.astimezone(timezone.utc), event_type, operation,
                 safe_ref, rejection_code(error)),
            )
