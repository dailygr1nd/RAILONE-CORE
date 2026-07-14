"""Encrypted account-endpoint and contact-destination resolvers."""

from __future__ import annotations

import hashlib

from .envelope import EnvelopeEncryptionService
from .models import EncryptionPurpose
from .store import EncryptedSecretRecord, EncryptedSecretStore


class EncryptedAccountEndpointVault:
    VAULT = "ACCOUNT_ENDPOINT"

    def __init__(self, *, encryption: EnvelopeEncryptionService, store: EncryptedSecretStore) -> None:
        self._encryption = encryption
        self._store = store

    def register(self, *, institution_id: str, account_binding_id: str, provider_reference: str) -> None:
        record_id = self._record_id(institution_id, account_binding_id)
        envelope = self._encryption.encrypt_text(
            purpose=EncryptionPurpose.ACCOUNT_ENDPOINT, record_id=record_id,
            owner_id=institution_id, field_name="provider_account_reference",
            plaintext=provider_reference,
        )
        self._store.put(EncryptedSecretRecord(
            vault_name=self.VAULT, record_id=record_id, owner_id=institution_id,
            envelope=envelope,
            plaintext_sha256=hashlib.sha256(provider_reference.encode("utf-8")).hexdigest(),
        ))

    def resolve(self, *, institution_id: str, account_binding_id: str) -> str:
        record_id = self._record_id(institution_id, account_binding_id)
        record = self._store.require(vault_name=self.VAULT, record_id=record_id)
        if record.owner_id != institution_id:
            raise PermissionError("account endpoint owner mismatch")
        return self._encryption.decrypt_text(
            envelope=record.envelope, purpose=EncryptionPurpose.ACCOUNT_ENDPOINT,
            record_id=record_id, owner_id=institution_id,
            field_name="provider_account_reference",
        )

    @staticmethod
    def _record_id(institution_id: str, account_binding_id: str) -> str:
        if not institution_id.strip() or not account_binding_id.strip():
            raise ValueError("institution and account binding identifiers are required")
        return f"{institution_id}:{account_binding_id}"


class EncryptedContactBindingVault:
    VAULT = "CONTACT_DESTINATION"

    def __init__(self, *, encryption: EnvelopeEncryptionService, store: EncryptedSecretStore) -> None:
        self._encryption = encryption
        self._store = store

    def register(self, *, contact_binding_id: str, owner_id: str, sms_destination: str) -> None:
        envelope = self._encryption.encrypt_text(
            purpose=EncryptionPurpose.CONTACT_DESTINATION,
            record_id=contact_binding_id, owner_id=owner_id,
            field_name="sms_destination", plaintext=sms_destination,
        )
        self._store.put(EncryptedSecretRecord(
            vault_name=self.VAULT, record_id=contact_binding_id, owner_id=owner_id,
            envelope=envelope,
            plaintext_sha256=hashlib.sha256(sms_destination.encode("utf-8")).hexdigest(),
        ))

    def resolve_sms_destination(self, contact_binding_id: str) -> str:
        record = self._store.require(
            vault_name=self.VAULT, record_id=contact_binding_id
        )
        return self._encryption.decrypt_text(
            envelope=record.envelope, purpose=EncryptionPurpose.CONTACT_DESTINATION,
            record_id=contact_binding_id, owner_id=record.owner_id,
            field_name="sms_destination",
        )


class EncryptedProviderCredentialVault:
    VAULT = "PROVIDER_CREDENTIAL"

    def __init__(self, *, encryption: EnvelopeEncryptionService, store: EncryptedSecretStore) -> None:
        self._encryption = encryption
        self._store = store

    def register(self, *, provider_id: str, credential_name: str, secret: str) -> None:
        record_id = self._record_id(provider_id, credential_name)
        envelope = self._encryption.encrypt_text(
            purpose=EncryptionPurpose.PROVIDER_CREDENTIAL,
            record_id=record_id, owner_id=provider_id,
            field_name=credential_name, plaintext=secret,
        )
        self._store.put(EncryptedSecretRecord(
            vault_name=self.VAULT, record_id=record_id, owner_id=provider_id,
            envelope=envelope,
            plaintext_sha256=hashlib.sha256(secret.encode("utf-8")).hexdigest(),
        ))

    def resolve(self, *, provider_id: str, credential_name: str) -> str:
        record_id = self._record_id(provider_id, credential_name)
        record = self._store.require(vault_name=self.VAULT, record_id=record_id)
        if record.owner_id != provider_id:
            raise PermissionError("provider credential owner mismatch")
        return self._encryption.decrypt_text(
            envelope=record.envelope, purpose=EncryptionPurpose.PROVIDER_CREDENTIAL,
            record_id=record_id, owner_id=provider_id, field_name=credential_name,
        )

    @staticmethod
    def _record_id(provider_id: str, credential_name: str) -> str:
        if not provider_id.strip() or not credential_name.strip():
            raise ValueError("provider and credential identifiers are required")
        return f"{provider_id}:{credential_name}"
