"""PostgreSQL quote-acceptance repository with atomic idempotency."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from railone_contracts.store import (
    AcceptedContract,
    ContractStore,
    IdempotencyConflictError,
    QuoteAlreadyAcceptedError,
    UttNotFoundError,
)
from railone_crypto.signature_service import SignatureEnvelope

from .codec import envelope_from_db, json_text
from .runtime import PostgresDatabase


_ACCEPTED_SELECT = """
SELECT u.quote_id, u.utt_id, u.signed_envelope,
       i.request_sha256, u.accepted_at, a.signed_envelope AS sender_authority
FROM railone.acceptance_idempotency i
JOIN railone.accepted_utts u ON u.utt_id = i.utt_id
JOIN railone.execution_authorities a
  ON a.utt_id = u.utt_id AND a.authority_type = 'ETK_S'
"""


class PostgresContractStore(ContractStore):
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    def resolve_idempotency(
        self, idempotency_key: str, request_sha256: str
    ) -> AcceptedContract | None:
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                _ACCEPTED_SELECT + " WHERE i.idempotency_key = %s",
                (idempotency_key,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            contract = _accepted(row)
            if contract.request_sha256 != request_sha256:
                raise IdempotencyConflictError(
                    "idempotency key was already used for different request material"
                )
            return contract

    def commit_acceptance(
        self, *, idempotency_key: str, contract: AcceptedContract
    ) -> tuple[AcceptedContract, bool]:
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                _ACCEPTED_SELECT + " WHERE i.idempotency_key = %s FOR UPDATE OF i",
                (idempotency_key,),
            )
            existing = cursor.fetchone()
            if existing is not None:
                accepted = _accepted(existing)
                if accepted.request_sha256 != contract.request_sha256:
                    raise IdempotencyConflictError(
                        "idempotency key was already used for different request material"
                    )
                return accepted, True

            utt = contract.signed_utt
            cursor.execute(
                """INSERT INTO railone.accepted_utts
                   (utt_id, quote_id, utt_payload_sha256, signed_envelope, accepted_at)
                   VALUES (%s,%s,%s,%s::jsonb,%s)
                   ON CONFLICT DO NOTHING
                   RETURNING utt_id""",
                (
                    contract.utt_id, contract.quote_id,
                    utt.protected["payload_sha256"], json_text(utt.to_dict()),
                    contract.accepted_at,
                ),
            )
            inserted = cursor.fetchone()
            if inserted is None:
                # ON CONFLICT waits for a concurrent winner.  Once it commits,
                # the matching idempotency record is visible in this READ
                # COMMITTED transaction and must return the original contract.
                cursor.execute(
                    _ACCEPTED_SELECT + " WHERE i.idempotency_key = %s",
                    (idempotency_key,),
                )
                concurrent = cursor.fetchone()
                if concurrent is not None:
                    accepted = _accepted(concurrent)
                    if accepted.request_sha256 != contract.request_sha256:
                        raise IdempotencyConflictError(
                            "idempotency key was already used for different request material"
                        )
                    return accepted, True
                cursor.execute(
                    "SELECT utt_id, quote_id FROM railone.accepted_utts WHERE quote_id = %s OR utt_id = %s",
                    (contract.quote_id, contract.utt_id),
                )
                collision = cursor.fetchone()
                prior_utt = "UNKNOWN" if collision is None else collision["utt_id"]
                raise QuoteAlreadyAcceptedError(f"quote already accepted as {prior_utt}")

            authority = contract.sender_authority
            authority_id = authority.payload.get("etk_s_id")
            if not isinstance(authority_id, str) or not authority_id:
                raise ValueError("ETK-S payload is missing etk_s_id")
            cursor.execute(
                """INSERT INTO railone.execution_authorities
                   (authority_id, authority_type, utt_id, payload_sha256,
                    signed_envelope, created_at)
                   VALUES (%s,'ETK_S',%s,%s,%s::jsonb,%s)""",
                (
                    authority_id, contract.utt_id,
                    authority.protected["payload_sha256"],
                    json_text(authority.to_dict()), contract.accepted_at,
                ),
            )
            cursor.execute(
                """INSERT INTO railone.acceptance_idempotency
                   (idempotency_key, request_sha256, utt_id, created_at)
                   VALUES (%s,%s,%s,%s)
                   ON CONFLICT (idempotency_key) DO NOTHING
                   RETURNING idempotency_key""",
                (
                    idempotency_key, contract.request_sha256,
                    contract.utt_id, contract.accepted_at,
                ),
            )
            if cursor.fetchone() is None:
                raise RuntimeError("acceptance idempotency race requires transaction retry")
            return contract, False

    def require_utt(self, utt_id: str) -> SignatureEnvelope:
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT signed_envelope FROM railone.accepted_utts WHERE utt_id = %s",
                (utt_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise UttNotFoundError(f"persisted UTT not found: {utt_id}")
            return envelope_from_db(row["signed_envelope"])


def _accepted(row: Mapping[str, Any]) -> AcceptedContract:
    return AcceptedContract(
        signed_utt=envelope_from_db(row["signed_envelope"]),
        sender_authority=envelope_from_db(row["sender_authority"]),
        quote_id=str(row["quote_id"]), utt_id=str(row["utt_id"]),
        request_sha256=str(row["request_sha256"]), accepted_at=row["accepted_at"],
    )
