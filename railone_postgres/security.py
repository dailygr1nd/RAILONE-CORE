"""PostgreSQL persistence for encrypted values; plaintext is never accepted."""

from __future__ import annotations

from railone_security.models import EncryptedEnvelope
from railone_security.store import EncryptedSecretRecord, EncryptedSecretStore

from .codec import json_object, json_text
from .runtime import PostgresDatabase


class PostgresEncryptedSecretStore(EncryptedSecretStore):
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    def put(self, record: EncryptedSecretRecord) -> EncryptedSecretRecord:
        record.envelope.validate()
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO railone.encrypted_secrets
                   (vault_name, record_id, owner_id, envelope, plaintext_sha256,
                    encryption_key_id, envelope_version)
                   VALUES (%s,%s,%s,%s::jsonb,%s,%s,%s)
                   ON CONFLICT (vault_name, record_id) DO NOTHING""",
                (
                    record.vault_name, record.record_id, record.owner_id,
                    json_text(record.envelope.to_dict()), record.plaintext_sha256,
                    record.envelope.key_id, record.envelope.version,
                ),
            )
            cursor.execute(
                """SELECT vault_name, record_id, owner_id, envelope,
                          plaintext_sha256
                   FROM railone.encrypted_secrets
                   WHERE vault_name=%s AND record_id=%s""",
                (record.vault_name, record.record_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("encrypted secret insert was incomplete")
            stored = _record(row)
            if stored != record:
                raise RuntimeError("encrypted secret immutability conflict")
            return stored

    def require(self, *, vault_name: str, record_id: str) -> EncryptedSecretRecord:
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT vault_name, record_id, owner_id, envelope,
                          plaintext_sha256
                   FROM railone.encrypted_secrets
                   WHERE vault_name=%s AND record_id=%s""",
                (vault_name, record_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise LookupError("encrypted secret was not found")
            return _record(row)


def _record(row) -> EncryptedSecretRecord:
    return EncryptedSecretRecord(
        vault_name=str(row["vault_name"]), record_id=str(row["record_id"]),
        owner_id=str(row["owner_id"]),
        envelope=EncryptedEnvelope.from_dict(json_object(row["envelope"])),
        plaintext_sha256=str(row["plaintext_sha256"]),
    )
