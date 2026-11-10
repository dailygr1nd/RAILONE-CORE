"""Publication-only bank analytics: no access to private route-decision data.

Writer and reader MUST use different DB credentials. Bank reads must connect as
an individually authenticated PostgreSQL LOGIN mapped by the security admin in
railone.bank_analytics_principals. The SQL view scopes by SESSION_USER, not a
client-supplied institution ID or writable application setting.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from .runtime import PostgresDatabase

_ALLOWED = frozenset({
    "OWN_UTT_SUBMITTED_TOTAL", "OWN_UTT_SETTLED_TOTAL",
    "OWN_SETTLEMENT_LATENCY_P95_MS", "OWN_PROVIDER_ACCEPTANCE_RATE_BPS",
})


def _time(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("metric reporting period requires aware UTC times")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class BankMetric:
    metric_name: str
    period_start: datetime
    period_end: datetime
    metric_value: int
    sample_count: int

    def __post_init__(self) -> None:
        if self.metric_name not in _ALLOWED:
            raise ValueError("metric is not approved for bank publication")
        if (_time(self.period_end) - _time(self.period_start)).total_seconds() < 86400:
            raise ValueError("bank publications cannot expose sub-day windows")
        for name in ("metric_value", "sample_count"):
            value = getattr(self, name)
            if type(value) is not int or value < 0 or value >= 2**63:
                raise ValueError(f"{name} must be a nonnegative bounded integer")
        if self.sample_count < 20:
            raise ValueError("insufficient cohort size for bank publication")
        if (self.metric_name == "OWN_PROVIDER_ACCEPTANCE_RATE_BPS"
                and self.metric_value > 10_000):
            raise ValueError("acceptance rate must be expressed in basis points")


class PostgresBankMetricsPublisher:
    """Trusted batch-only service; DB principal must NOT be bank read-only."""

    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    def publish(self, *, institution_id: str, metric: BankMetric,
                approved_by: str) -> str:
        # Caller/approval authentication belongs to the trusted publishing job;
        # source data MUST be aggregated from the institution's own transactions.
        if not isinstance(institution_id, str) or not 3 <= len(institution_id) <= 128:
            raise ValueError("institution id is invalid")
        if not isinstance(approved_by, str) or not 3 <= len(approved_by) <= 128:
            raise ValueError("approval identity required")
        publication_id = "PUB-" + uuid4().hex.upper()
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO railone.bank_analytics_publications
                   (publication_id,institution_id,metric_name,period_start,period_end,
                    metric_value,sample_count,approved_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (publication_id, institution_id, metric.metric_name,
                 _time(metric.period_start), _time(metric.period_end),
                 metric.metric_value, metric.sample_count, approved_by),
            )
        return publication_id

    def withdraw(self, *, publication_id: str, reason_code: str) -> None:
        if reason_code not in {"CORRECTION", "PRIVACY", "POLICY"}:
            raise ValueError("publication withdrawal reason must be allowlisted")
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO railone.bank_analytics_withdrawals
                   (publication_id,reason_code) VALUES (%s,%s)""",
                (publication_id, reason_code),
            )


class PostgresBankMetricsReader:
    """Read only the pre-approved security-barrier view, never operational tables.

    Use a dedicated bank-specific DB login. No caller-supplied institution filter
    is accepted. The database itself is the bank identity and access boundary.
    """

    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    def list_metrics(self, *, limit: int = 100) -> tuple[BankMetric, ...]:
        if type(limit) is not int or not 1 <= limit <= 365:
            raise ValueError("metric read limit must be between 1 and 365")
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT metric_name,period_start,period_end,metric_value,sample_count
                   FROM railone_bank.metrics ORDER BY period_end DESC,metric_name
                   LIMIT %s""", (limit,),
            )
            rows = cursor.fetchall()
        return tuple(BankMetric(**dict(row)) for row in rows)
