"""PostgreSQL implementation of the identity continuity repository."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from railone_identity.continuity import IdentityRepository
from railone_identity.models import (
    IdentityBundle,
    IdentityGenesis,
    IdentityObject,
    IdentityRevision,
    IdentityStatus,
    TrustTier,
)

from .runtime import PostgresDatabase


_BUNDLE_SELECT = """
SELECT g.rig_id, g.continuity_uid, g.continuity_key_id,
       g.identity_fingerprint, g.verification_provider_id,
       g.verification_reference, g.evidence_sha256,
       g.attestation_id AS genesis_attestation_id, g.created_at AS genesis_created_at,
       o.rio_id, o.railone_id, o.active_riv_id, o.corridor,
       o.status AS identity_status, o.created_at AS identity_created_at,
       r.revision, r.trust_tier, r.status AS revision_status,
       r.reason, r.attestation_id AS revision_attestation_id,
       r.created_at AS revision_created_at
FROM railone.identity_genesis g
JOIN railone.identity_objects o ON o.continuity_uid = g.continuity_uid
JOIN railone.identity_revisions r
  ON r.rio_id = o.rio_id AND r.riv_id = o.active_riv_id
"""


class PostgresIdentityRepository(IdentityRepository):
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    def get_by_fingerprint(self, fingerprint: str) -> IdentityBundle | None:
        return self._one(_BUNDLE_SELECT + " WHERE g.identity_fingerprint = %s", (fingerprint,))

    def get_by_continuity_uid(self, continuity_uid: str) -> IdentityBundle | None:
        return self._one(_BUNDLE_SELECT + " WHERE g.continuity_uid = %s", (continuity_uid,))

    def list_revisions(self, continuity_uid: str) -> tuple[IdentityRevision, ...]:
        query = """
        SELECT riv_id, rio_id, continuity_uid, revision, trust_tier, status,
               reason, attestation_id, created_at
        FROM railone.identity_revisions
        WHERE continuity_uid = %s
        ORDER BY revision
        """
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(query, (continuity_uid,))
            return tuple(_revision(row) for row in cursor.fetchall())

    def save(self, bundle: IdentityBundle) -> None:
        genesis = bundle.genesis
        identity = bundle.identity
        revision = bundle.active_revision
        if revision.revision != 1:
            raise ValueError("new continuity identity must begin at revision 1")
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO railone.identity_genesis
                   (rig_id, continuity_uid, continuity_key_id, identity_fingerprint,
                    verification_provider_id, verification_reference, evidence_sha256,
                    attestation_id, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    genesis.rig_id, genesis.continuity_uid,
                    genesis.continuity_key_id, genesis.identity_fingerprint,
                    genesis.verification_provider_id, genesis.verification_reference,
                    genesis.evidence_sha256, genesis.attestation_id, genesis.created_at,
                ),
            )
            cursor.execute(
                """INSERT INTO railone.identity_objects
                   (rio_id, railone_id, continuity_uid, rig_id, active_riv_id,
                    active_revision, corridor, status, projection_version,
                    created_at, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,1,%s,%s)""",
                (
                    identity.rio_id, identity.railone_id, identity.continuity_uid,
                    identity.rig_id, identity.active_riv_id, revision.revision,
                    identity.corridor, identity.status.value, identity.created_at,
                    identity.created_at,
                ),
            )
            self._insert_revision(cursor, revision)

    def append_revision(
        self, *, expected_revision: int, bundle: IdentityBundle
    ) -> None:
        revision = bundle.active_revision
        if revision.revision != expected_revision + 1:
            raise ValueError("identity revision must advance exactly once")
        with self._database.transaction() as connection, connection.cursor() as cursor:
            self._insert_revision(cursor, revision)
            cursor.execute(
                """UPDATE railone.identity_objects
                   SET active_riv_id = %s, active_revision = %s, status = %s,
                       projection_version = projection_version + 1, updated_at = %s
                   WHERE rio_id = %s AND continuity_uid = %s
                     AND active_revision = %s AND status <> 'REVOKED'""",
                (
                    revision.riv_id, revision.revision, revision.status.value,
                    revision.created_at, bundle.identity.rio_id,
                    bundle.identity.continuity_uid, expected_revision,
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("identity revision changed concurrently")

    def _one(self, query: str, params: tuple[object, ...]) -> IdentityBundle | None:
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(query, params)
            row = cursor.fetchone()
            return None if row is None else _bundle(row)

    @staticmethod
    def _insert_revision(cursor, revision: IdentityRevision) -> None:
        cursor.execute(
            """INSERT INTO railone.identity_revisions
               (riv_id, rio_id, continuity_uid, revision, trust_tier, status,
                reason, attestation_id, created_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                revision.riv_id, revision.rio_id, revision.continuity_uid,
                revision.revision, revision.trust_tier.value, revision.status.value,
                revision.reason, revision.attestation_id, revision.created_at,
            ),
        )


def _bundle(row: Mapping[str, Any]) -> IdentityBundle:
    continuity_uid = str(row["continuity_uid"])
    return IdentityBundle(
        genesis=IdentityGenesis(
            rig_id=str(row["rig_id"]), continuity_uid=continuity_uid,
            continuity_key_id=str(row["continuity_key_id"]),
            identity_fingerprint=str(row["identity_fingerprint"]),
            verification_provider_id=str(row["verification_provider_id"]),
            verification_reference=str(row["verification_reference"]),
            evidence_sha256=str(row["evidence_sha256"]),
            attestation_id=str(row["genesis_attestation_id"]),
            created_at=row["genesis_created_at"],
        ),
        identity=IdentityObject(
            rio_id=str(row["rio_id"]), railone_id=str(row["railone_id"]),
            continuity_uid=continuity_uid, rig_id=str(row["rig_id"]),
            active_riv_id=str(row["active_riv_id"]), corridor=str(row["corridor"]),
            status=IdentityStatus(row["identity_status"]),
            created_at=row["identity_created_at"],
        ),
        active_revision=IdentityRevision(
            riv_id=str(row["active_riv_id"]), rio_id=str(row["rio_id"]),
            continuity_uid=continuity_uid, revision=int(row["revision"]),
            trust_tier=TrustTier(row["trust_tier"]),
            status=IdentityStatus(row["revision_status"]), reason=str(row["reason"]),
            attestation_id=str(row["revision_attestation_id"]),
            created_at=row["revision_created_at"],
        ),
    )


def _revision(row: Mapping[str, Any]) -> IdentityRevision:
    return IdentityRevision(
        riv_id=str(row["riv_id"]), rio_id=str(row["rio_id"]),
        continuity_uid=str(row["continuity_uid"]), revision=int(row["revision"]),
        trust_tier=TrustTier(row["trust_tier"]),
        status=IdentityStatus(row["status"]), reason=str(row["reason"]),
        attestation_id=str(row["attestation_id"]), created_at=row["created_at"],
    )
