"""Append-only PostgreSQL persistence for signed adapter capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from railone_crypto.canonical_json import canonical_json_bytes
from railone_institutions.models import SignedCapabilityManifest

from .codec import json_object, json_text
from .runtime import PostgresDatabase


@dataclass(frozen=True, slots=True)
class StoredAdapterManifest:
    adapter_id: str
    adapter_version: str
    provider_id: str
    signed_manifest: Mapping[str, object]
    payload_sha256: str
    issued_at: datetime
    expires_at: datetime


class PostgresInstitutionManifestStore:
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    def put(self, signed: SignedCapabilityManifest) -> StoredAdapterManifest:
        manifest = signed.manifest
        descriptor = manifest.descriptor
        envelope = signed.signature.to_dict()
        payload_hash = str(envelope["protected"]["payload_sha256"])
        if canonical_json_bytes(envelope["payload"]) != canonical_json_bytes(manifest.to_payload()):
            raise ValueError("manifest object differs from signed payload")
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO railone.institution_adapter_manifests
                   (adapter_id, adapter_version, provider_id, network_id,
                    environment, certification_status, manifest_id,
                    manifest_version, signed_manifest, payload_sha256,
                    signing_key_id, issued_at, expires_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)
                   ON CONFLICT (adapter_id, adapter_version) DO NOTHING""",
                (
                    descriptor.adapter_id, descriptor.adapter_version,
                    descriptor.provider_id, descriptor.network_id,
                    descriptor.environment.value, descriptor.certification_status.value,
                    manifest.manifest_id, manifest.manifest_version,
                    json_text(envelope), payload_hash,
                    envelope["protected"]["kid"], manifest.issued_at, manifest.expires_at,
                ),
            )
        stored = self.require(descriptor.binding_ref)
        if stored.payload_sha256 != payload_hash or dict(stored.signed_manifest) != envelope:
            raise RuntimeError("institution manifest immutability conflict")
        return stored

    def require(self, binding_ref: str) -> StoredAdapterManifest:
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT adapter_id, adapter_version, provider_id,
                          signed_manifest, payload_sha256, issued_at, expires_at
                   FROM railone.institution_adapter_manifests
                   WHERE binding_ref=%s""",
                (binding_ref,),
            )
            row = cursor.fetchone()
            if row is None:
                raise LookupError("institution adapter manifest not found")
            return StoredAdapterManifest(
                adapter_id=str(row["adapter_id"]),
                adapter_version=str(row["adapter_version"]),
                provider_id=str(row["provider_id"]),
                signed_manifest=json_object(row["signed_manifest"]),
                payload_sha256=str(row["payload_sha256"]),
                issued_at=row["issued_at"], expires_at=row["expires_at"],
            )
