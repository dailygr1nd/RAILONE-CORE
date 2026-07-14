from __future__ import annotations

import secrets
import unittest
from dataclasses import replace

from railone_security import (
    EncryptionPurpose, EnvelopeEncryptionService, EnvelopeIntegrityError,
    InMemoryAesGcmKeyEncryptionProvider,
)


def encryption_fixture():
    keys = InMemoryAesGcmKeyEncryptionProvider()
    active = {}
    for purpose in EncryptionPurpose:
        key_id = f"test-{purpose.value.lower()}-v1"
        keys.register(key_id=key_id, key=secrets.token_bytes(32))
        active[purpose] = key_id
    return keys, active, EnvelopeEncryptionService(keys=keys, active_key_ids=active)


class EnvelopeEncryptionTests(unittest.TestCase):
    def test_round_trip_uses_randomized_ciphertext(self):
        _, _, service = encryption_fixture()
        values = [service.encrypt_text(
            purpose=EncryptionPurpose.ACCOUNT_ENDPOINT,
            record_id="BANK-001:BIND-001", owner_id="BANK-001",
            field_name="provider_account_reference", plaintext="SIM-ACC-123",
        ) for _ in range(2)]
        self.assertNotEqual(values[0].nonce, values[1].nonce)
        self.assertNotEqual(values[0].ciphertext, values[1].ciphertext)
        for envelope in values:
            self.assertEqual(service.decrypt_text(
                envelope=envelope, purpose=EncryptionPurpose.ACCOUNT_ENDPOINT,
                record_id="BANK-001:BIND-001", owner_id="BANK-001",
                field_name="provider_account_reference",
            ), "SIM-ACC-123")

    def test_context_and_purpose_are_authenticated(self):
        _, _, service = encryption_fixture()
        envelope = service.encrypt_text(
            purpose=EncryptionPurpose.CONTACT_DESTINATION,
            record_id="CONTACT-1", owner_id="CONT-1",
            field_name="sms_destination", plaintext="SIM-254700000001",
        )
        with self.assertRaises(EnvelopeIntegrityError):
            service.decrypt_text(
                envelope=envelope, purpose=EncryptionPurpose.CONTACT_DESTINATION,
                record_id="CONTACT-2", owner_id="CONT-1",
                field_name="sms_destination",
            )
        with self.assertRaises(EnvelopeIntegrityError):
            service.decrypt_text(
                envelope=envelope, purpose=EncryptionPurpose.ACCOUNT_ENDPOINT,
                record_id="CONTACT-1", owner_id="CONT-1",
                field_name="sms_destination",
            )

    def test_ciphertext_and_wrapped_key_tampering_fail_closed(self):
        _, _, service = encryption_fixture()
        envelope = service.encrypt_text(
            purpose=EncryptionPurpose.PROVIDER_CREDENTIAL,
            record_id="CRED-1", owner_id="MPESA-KE",
            field_name="credential", plaintext="synthetic-secret",
        )
        flip = lambda value: ("A" if value[0] != "A" else "B") + value[1:]
        for changed in (
            replace(envelope, ciphertext=flip(envelope.ciphertext)),
            replace(envelope, wrapped_data_key=flip(envelope.wrapped_data_key)),
        ):
            with self.assertRaises(EnvelopeIntegrityError):
                service.decrypt_text(
                    envelope=changed, purpose=EncryptionPurpose.PROVIDER_CREDENTIAL,
                    record_id="CRED-1", owner_id="MPESA-KE",
                    field_name="credential",
                )

    def test_key_rotation_preserves_old_envelope_verification(self):
        keys, active, old_service = encryption_fixture()
        old = old_service.encrypt_text(
            purpose=EncryptionPurpose.ACCOUNT_ENDPOINT,
            record_id="I:B", owner_id="I", field_name="provider_account_reference",
            plaintext="SIM-OLD",
        )
        rotated = dict(active)
        rotated_id = "test-account-endpoint-v2"
        keys.register(key_id=rotated_id, key=secrets.token_bytes(32))
        rotated[EncryptionPurpose.ACCOUNT_ENDPOINT] = rotated_id
        new_service = EnvelopeEncryptionService(keys=keys, active_key_ids=rotated)
        self.assertEqual(new_service.decrypt_text(
            envelope=old, purpose=EncryptionPurpose.ACCOUNT_ENDPOINT,
            record_id="I:B", owner_id="I", field_name="provider_account_reference",
        ), "SIM-OLD")
        new = new_service.encrypt_text(
            purpose=EncryptionPurpose.ACCOUNT_ENDPOINT,
            record_id="I:B2", owner_id="I", field_name="provider_account_reference",
            plaintext="SIM-NEW",
        )
        self.assertEqual(new.key_id, rotated_id)


if __name__ == "__main__":
    unittest.main()
