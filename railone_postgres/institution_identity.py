"""Durable R1-IOS-001 identity registry; verification uses service-layer signatures."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Mapping

from railone_crypto.canonical_json import canonical_json_bytes
from railone_crypto.signature_service import SignatureEnvelope
from railone_institutions.identity import (
    IdentityAdmissionState, InstitutionApplication, InstitutionClass, InstitutionIdentityRecord,
)

from .codec import envelope_from_db, json_text
from .runtime import PostgresDatabase


class PostgresInstitutionIdentityRepository:
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    def insert(self, record: InstitutionIdentityRecord) -> None:
        if record.status is not IdentityAdmissionState.PENDING_VERIFICATION:
            raise PermissionError("unverified institution registration required")
        app = record.application
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO railone.institution_identity_registry
                   (institution_id,legal_name,display_name,institution_class,home_jurisdiction,
                    registration_reference,regulatory_evidence_refs,identity_state,submitted_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (record.institution_id, app.legal_name, app.display_name,
                 app.institution_class.value, app.home_jurisdiction,
                 app.registration_reference, list(app.regulatory_evidence_refs),
                 record.status.value, record.submitted_at),
            )

    def get(self, institution_id: str) -> InstitutionIdentityRecord | None:
        return self._query("institution_id=%s", (institution_id,))

    def find_registration(self, jurisdiction: str, registration_reference: str) -> InstitutionIdentityRecord | None:
        return self._query("home_jurisdiction=%s AND registration_reference=%s",
                           (jurisdiction, registration_reference))

    def _query(self, predicate: str, args: tuple[str, ...]) -> InstitutionIdentityRecord | None:
        # Predicate is internal constant from two call sites, never user-controlled SQL.
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT institution_id,legal_name,display_name,institution_class,home_jurisdiction,
                          registration_reference,regulatory_evidence_refs,identity_state,
                          submitted_at,verified_at,signed_verification
                   FROM railone.institution_identity_registry WHERE """ + predicate, args)
            row = cursor.fetchone()
        return _record(row) if row is not None else None

    def record_verification(self, institution_id: str, evidence: SignatureEnvelope,
                            verified_at: datetime) -> InstitutionIdentityRecord:
        envelope = evidence.to_dict()
        event_sha256 = hashlib.sha256(canonical_json_bytes(envelope)).hexdigest()
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """UPDATE railone.institution_identity_registry
                   SET identity_state='VERIFIED',signed_verification=%s::jsonb,verified_at=%s
                   WHERE institution_id=%s AND identity_state='PENDING_VERIFICATION'""",
                (json_text(envelope), verified_at, institution_id),
            )
            if cursor.rowcount != 1:
                raise PermissionError("institutional identity was not pending verification")
            cursor.execute(
                """INSERT INTO railone.institution_identity_verification_events
                   (event_sha256,institution_id,signed_verification,recorded_at)
                   VALUES (%s,%s,%s::jsonb,%s)""",
                (event_sha256, institution_id, json_text(envelope), verified_at),
            )
        record = self.get(institution_id)
        if record is None:
            raise RuntimeError("verified institutional identity could not be read")
        return record


def _record(row: Mapping[str, object]) -> InstitutionIdentityRecord:
    application = InstitutionApplication(
        legal_name=str(row["legal_name"]), display_name=str(row["display_name"]),
        institution_class=InstitutionClass(row["institution_class"]),
        home_jurisdiction=str(row["home_jurisdiction"]).strip(),
        registration_reference=str(row["registration_reference"]),
        regulatory_evidence_refs=tuple(row["regulatory_evidence_refs"]),
    )
    signed = row["signed_verification"]
    return InstitutionIdentityRecord(
        institution_id=str(row["institution_id"]), application=application,
        status=IdentityAdmissionState(row["identity_state"]),
        submitted_at=row["submitted_at"],
        signed_verification=envelope_from_db(signed) if signed is not None else None,
        verified_at=row["verified_at"],
    )
