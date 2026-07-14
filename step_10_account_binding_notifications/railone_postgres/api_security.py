"""PostgreSQL access-token revocation, rate-limit, and API audit stores."""

from __future__ import annotations

from datetime import datetime, timedelta

from railone_api.auth import TokenRevocationStore
from railone_api.guard import (
    ApiAuditStore,
    ApiRequestAudit,
    RateLimitDecision,
    RateLimitStore,
    _rate_policy,
)

from .codec import json_text
from .runtime import PostgresDatabase


class PostgresTokenRevocationStore(TokenRevocationStore):
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    def is_revoked(self, token_id: str) -> bool:
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM railone.api_token_revocations WHERE token_id=%s",
                (token_id,),
            )
            return cursor.fetchone() is not None

    def revoke(
        self, *, token_id: str, expires_at: datetime, reason: str, at: datetime
    ) -> None:
        normalized_reason = reason.strip().upper()
        if not normalized_reason:
            raise ValueError("token revocation reason is required")
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO railone.api_token_revocations
                   (token_id, expires_at, reason, revoked_at)
                   VALUES (%s,%s,%s,%s)
                   ON CONFLICT (token_id) DO NOTHING RETURNING token_id""",
                (token_id, expires_at, normalized_reason, at),
            )
            if cursor.fetchone() is not None:
                return
            cursor.execute(
                """SELECT expires_at, reason FROM railone.api_token_revocations
                   WHERE token_id=%s""",
                (token_id,),
            )
            existing = cursor.fetchone()
            if (
                existing is None
                or existing["expires_at"] != expires_at
                or existing["reason"] != normalized_reason
            ):
                raise RuntimeError("token revocation conflict")


class PostgresRateLimitStore(RateLimitStore):
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    def consume(
        self, *, scope_key: str, limit: int, window_seconds: int, at: datetime
    ) -> RateLimitDecision:
        _rate_policy(limit, window_seconds)
        if not scope_key.strip():
            raise ValueError("rate-limit scope key is required")
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO railone.api_rate_limit_windows
                   (scope_key, window_started_at, window_seconds, request_count, updated_at)
                   VALUES (%s,%s,%s,1,%s)
                   ON CONFLICT (scope_key) DO UPDATE SET
                     window_started_at = CASE
                       WHEN railone.api_rate_limit_windows.window_started_at
                            + make_interval(secs => railone.api_rate_limit_windows.window_seconds)
                            <= EXCLUDED.updated_at
                       THEN EXCLUDED.window_started_at
                       ELSE railone.api_rate_limit_windows.window_started_at END,
                     window_seconds = CASE
                       WHEN railone.api_rate_limit_windows.window_started_at
                            + make_interval(secs => railone.api_rate_limit_windows.window_seconds)
                            <= EXCLUDED.updated_at
                       THEN EXCLUDED.window_seconds
                       ELSE railone.api_rate_limit_windows.window_seconds END,
                     request_count = CASE
                       WHEN railone.api_rate_limit_windows.window_started_at
                            + make_interval(secs => railone.api_rate_limit_windows.window_seconds)
                            <= EXCLUDED.updated_at
                       THEN 1 ELSE railone.api_rate_limit_windows.request_count + 1 END,
                     updated_at = EXCLUDED.updated_at
                   RETURNING window_started_at, window_seconds, request_count""",
                (scope_key, at, window_seconds, at),
            )
            row = cursor.fetchone()
            count = int(row["request_count"])
            reset_at = row["window_started_at"] + timedelta(
                seconds=int(row["window_seconds"])
            )
            return RateLimitDecision(
                allowed=count <= limit, limit=limit,
                remaining=max(0, limit - count), reset_at=reset_at,
            )


class PostgresApiAuditStore(ApiAuditStore):
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    def append(self, audit: ApiRequestAudit) -> None:
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO railone.api_request_audit
                   (audit_id, request_id, principal_id, token_id, method,
                    route_template, outcome, status_code, reason_code,
                    occurred_at, audit_payload_sha256, signed_audit)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)""",
                (
                    audit.audit_id, audit.request_id, audit.principal_id,
                    audit.token_id, audit.method, audit.route_template,
                    audit.outcome.value, audit.status_code, audit.reason_code,
                    audit.occurred_at,
                    audit.signed_audit.protected["payload_sha256"],
                    json_text(audit.signed_audit.to_dict()),
                ),
            )
