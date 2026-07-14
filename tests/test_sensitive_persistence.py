from __future__ import annotations

import json
import unittest
from dataclasses import replace
from datetime import datetime, timezone

from railone_notifications import (
    NotificationRecipientRole, SmsDeliveryState, SmsNotificationRecord,
)
from railone_postgres.notifications import (
    PostgresSettlementNotificationStore, _notification, _notification_params,
)
from railone_providers import EncryptedMpesaCredentialProvider
from railone_security import (
    EncryptedProviderCredentialVault, InMemoryEncryptedSecretStore,
    NotificationBodyProtector,
)

from tests.test_envelope_encryption import encryption_fixture


class SensitivePersistenceTests(unittest.TestCase):
    def test_mpesa_credentials_resolve_from_encrypted_vault(self):
        _, _, encryption = encryption_fixture()
        store = InMemoryEncryptedSecretStore()
        vault = EncryptedProviderCredentialVault(
            encryption=encryption, store=store
        )
        expected = {
            "consumer_key": "SIM-CONSUMER",
            "consumer_secret": "SIM-SECRET",
            "initiator_name": "SIM-INITIATOR",
            "security_credential": "SIM-CREDENTIAL",
            "business_shortcode": "600000",
        }
        for name, value in expected.items():
            vault.register(provider_id="MPESA-KE", credential_name=name, secret=value)
            record = store.require(
                vault_name="PROVIDER_CREDENTIAL", record_id=f"MPESA-KE:{name}"
            )
            self.assertNotIn(value, json.dumps(record.envelope.to_dict()))
        credentials = EncryptedMpesaCredentialProvider(vault).get()
        self.assertEqual(credentials.consumer_key, expected["consumer_key"])
        self.assertEqual(credentials.consumer_secret, expected["consumer_secret"])
        self.assertEqual(credentials.security_credential, expected["security_credential"])

    def test_postgres_notification_shape_contains_no_plaintext_body(self):
        _, _, encryption = encryption_fixture()
        protector = NotificationBodyProtector(encryption)
        now = datetime(2026, 7, 14, 20, 0, tzinfo=timezone.utc)
        source = SmsNotificationRecord(
            notification_id="SMS-001", evidence_id="SET-001", utt_id="UTT-001",
            recipient_role=NotificationRecipientRole.SENDER,
            contact_binding_id="CONTACT-001", template_version="settled-sms-v1",
            rendered_body="RailOne: SETTLED. SIM payment complete.",
            body_sha256="b4a2e49d51995690aadf70e7e7342a9f14c8722531af81b5566b0dd3c208898a",
            state=SmsDeliveryState.PREPARED, version=1,
            created_at=now, updated_at=now,
        )
        # Use the real fingerprint; the fixed value above is deliberately not trusted.
        import hashlib
        source = replace(
            source, body_sha256=hashlib.sha256(
                source.rendered_body.encode("utf-8")
            ).hexdigest()
        )
        params = _notification_params(source, protector)
        self.assertEqual(params[6], "[ENCRYPTED]")
        self.assertNotIn(source.rendered_body, json.dumps(params, default=str))
        row = {
            "notification_id": params[0], "evidence_id": params[1],
            "utt_id": params[2], "recipient_role": params[3],
            "contact_binding_id": params[4], "template_version": params[5],
            "rendered_body": params[6], "body_sha256": params[7],
            "state": params[8], "gateway_reference": params[9],
            "normalized_code": params[10], "version": params[11],
            "created_at": params[12], "updated_at": params[13],
            "rendered_body_envelope": params[14],
            "body_encryption_key_id": params[15],
            "body_envelope_version": params[16],
        }
        restored = _notification(row, protector)
        self.assertEqual(restored.rendered_body, source.rendered_body)

    def test_deployed_notification_store_fails_closed_without_protector(self):
        with self.assertRaisesRegex(ValueError, "requires body encryption"):
            PostgresSettlementNotificationStore(
                object(), require_encrypted_bodies=True
            )


if __name__ == "__main__":
    unittest.main()
