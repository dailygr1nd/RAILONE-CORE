"""PostgreSQL exactly-once provider outcome projection store."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from railone_projection.models import ProviderOutcomeProjection, ProviderProgressState
from railone_projection.store import (
    ProjectionEventConflictError,
    ProviderOutcomeProjectionStore,
)

from .runtime import PostgresDatabase


_COLUMNS = """submission_id, utt_id, rtt_id, provider_id, state,
normalized_code, external_reference, rejection_disposition, submission_version,
source_event_id, occurred_at, projected_at"""


class PostgresProviderOutcomeProjectionStore(ProviderOutcomeProjectionStore):
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    def apply(
        self,
        *,
        event_id: str,
        event_payload_sha256: str,
        projection: ProviderOutcomeProjection,
    ) -> bool:
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO railone.projection_inbox
                   (consumer_name, event_id, event_payload_sha256, consumed_at)
                   VALUES ('provider-outcome-v1',%s,%s,%s)
                   ON CONFLICT (consumer_name, event_id) DO NOTHING
                   RETURNING event_id""",
                (event_id, event_payload_sha256, projection.projected_at),
            )
            if cursor.fetchone() is None:
                cursor.execute(
                    """SELECT event_payload_sha256 FROM railone.projection_inbox
                       WHERE consumer_name='provider-outcome-v1' AND event_id=%s""",
                    (event_id,),
                )
                existing = cursor.fetchone()
                if existing is None or existing["event_payload_sha256"] != event_payload_sha256:
                    raise ProjectionEventConflictError(
                        "event identifier was reused with different signed material"
                    )
                return False
            cursor.execute(
                f"""INSERT INTO railone.provider_outcome_projections ({_COLUMNS})
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (submission_id) DO UPDATE SET
                      utt_id=EXCLUDED.utt_id, rtt_id=EXCLUDED.rtt_id,
                      provider_id=EXCLUDED.provider_id, state=EXCLUDED.state,
                      normalized_code=EXCLUDED.normalized_code,
                      external_reference=EXCLUDED.external_reference,
                      rejection_disposition=EXCLUDED.rejection_disposition,
                      submission_version=EXCLUDED.submission_version,
                      source_event_id=EXCLUDED.source_event_id,
                      occurred_at=EXCLUDED.occurred_at,
                      projected_at=EXCLUDED.projected_at
                    WHERE railone.provider_outcome_projections.submission_version
                          < EXCLUDED.submission_version""",
                _params(projection),
            )
            return True

    def get(self, submission_id: str) -> ProviderOutcomeProjection | None:
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {_COLUMNS} FROM railone.provider_outcome_projections WHERE submission_id=%s",
                (submission_id,),
            )
            row = cursor.fetchone()
            return None if row is None else _projection(row)


def _params(value: ProviderOutcomeProjection) -> tuple[object, ...]:
    return (
        value.submission_id, value.utt_id, value.rtt_id, value.provider_id,
        value.state.value, value.normalized_code, value.external_reference,
        value.rejection_disposition, value.submission_version,
        value.source_event_id, value.occurred_at, value.projected_at,
    )


def _projection(row: Mapping[str, Any]) -> ProviderOutcomeProjection:
    return ProviderOutcomeProjection(
        submission_id=str(row["submission_id"]), utt_id=str(row["utt_id"]),
        rtt_id=str(row["rtt_id"]), provider_id=str(row["provider_id"]),
        state=ProviderProgressState(row["state"]),
        normalized_code=row["normalized_code"],
        external_reference=row["external_reference"],
        rejection_disposition=row["rejection_disposition"],
        submission_version=int(row["submission_version"]),
        source_event_id=str(row["source_event_id"]),
        occurred_at=row["occurred_at"], projected_at=row["projected_at"],
    )
