"""Append-only PostgreSQL storage for prevalidated signed dispatch wrappers.

Requires migration 0013. Each put verifies the signature and independently
provided expected RailOne values; the store itself never dispatches funds.
"""

from __future__ import annotations

from datetime import datetime, timezone

from railone_crypto.signature_service import SignatureEnvelope
from railone_institutions.wrapper import (
    AuthoritativeDispatchSnapshot, CanonicalDispatchWrapper,
    DispatchWrapperService, SignedDispatchWrapper,
)

from .codec import json_object, json_text
from .runtime import PostgresDatabase


class PostgresDispatchWrapperStore:
    def __init__(self, database: PostgresDatabase, verifier: DispatchWrapperService) -> None:
        self._database = database
        self._verifier = verifier

    def put(
        self, signed: SignedDispatchWrapper, *, expected: AuthoritativeDispatchSnapshot,
        at: datetime,
    ) -> SignedDispatchWrapper:
        wrapper = self._verifier.verify(signed, expected=expected, at=at)
        body = wrapper.to_payload()
        trace = body["trace_identifiers"]
        binding = body["execution_binding"]
        signed_json = signed.signature.to_dict()
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO railone.institution_dispatch_wrappers
                   (envelope_id, rtt_id, plan_id, utt_id, route_decision_sha256,
                    adapter_binding_ref, wrapper_sha256, signed_artifact,
                    signing_key_id, issued_at, expires_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)
                   ON CONFLICT (rtt_id) DO NOTHING""",
                (body["envelope_id"], trace["rtt_id"], trace["plan_id"], trace["utt_id"],
                 binding["route_decision_digest"], binding["adapter_binding_ref"],
                 wrapper.wrapper_sha256, json_text(signed_json), signed_json["protected"]["kid"],
                 datetime.fromtimestamp(body["issued_at_epoch"], tz=timezone.utc),
                 datetime.fromtimestamp(body["expires_at_epoch"], tz=timezone.utc)),
            )
        stored = self.require(trace["rtt_id"])
        if (stored.wrapper != signed.wrapper or
            stored.signature.to_dict() != signed.signature.to_dict()):
            raise RuntimeError("signed wrapper immutability conflict")
        return stored

    def require(self, rtt_id: str) -> SignedDispatchWrapper:
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT signed_artifact, wrapper_sha256
                   FROM railone.institution_dispatch_wrappers WHERE rtt_id = %s""", (rtt_id,),
            )
            row = cursor.fetchone()
        if row is None:
            raise LookupError("signed dispatch wrapper not found")
        signature = SignatureEnvelope.from_dict(json_object(row["signed_artifact"]))
        wrapper = CanonicalDispatchWrapper.from_payload(signature.payload)
        if wrapper.wrapper_sha256 != str(row["wrapper_sha256"]):
            raise ValueError("database wrapper digest mismatch")
        return SignedDispatchWrapper(wrapper, signature)
