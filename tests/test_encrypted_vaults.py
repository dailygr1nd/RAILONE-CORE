from __future__ import annotations

import json
import unittest

from railone_security import (
    EncryptedAccountEndpointVault, EncryptedContactBindingVault,
    InMemoryEncryptedSecretStore,
)

from tests.test_envelope_encryption import encryption_fixture


class EncryptedVaultTests(unittest.TestCase):
    def setUp(self):
        _, _, encryption = encryption_fixture()
        self.store = InMemoryEncryptedSecretStore()
        self.accounts = EncryptedAccountEndpointVault(
            encryption=encryption, store=self.store
        )
        self.contacts = EncryptedContactBindingVault(
            encryption=encryption, store=self.store
        )

    def test_endpoint_resolves_only_inside_vault_boundary(self):
        self.accounts.register(
            institution_id="BANK-001", account_binding_id="BIND-001",
            provider_reference="SIM-ACCOUNT-999",
        )
        record = self.store.require(
            vault_name="ACCOUNT_ENDPOINT", record_id="BANK-001:BIND-001"
        )
        serialized = json.dumps(record.envelope.to_dict())
        self.assertNotIn("SIM-ACCOUNT-999", serialized)
        self.assertEqual(self.accounts.resolve(
            institution_id="BANK-001", account_binding_id="BIND-001"
        ), "SIM-ACCOUNT-999")
        with self.assertRaises(LookupError):
            self.accounts.resolve(
                institution_id="BANK-002", account_binding_id="BIND-001"
            )

    def test_contact_vault_implements_sms_resolver_contract(self):
        self.contacts.register(
            contact_binding_id="CONTACT-001", owner_id="CONTUID-001",
            sms_destination="SIM-254700000001",
        )
        self.assertEqual(
            self.contacts.resolve_sms_destination("CONTACT-001"),
            "SIM-254700000001",
        )

    def test_encrypted_records_are_immutable(self):
        self.contacts.register(
            contact_binding_id="CONTACT-001", owner_id="CONTUID-001",
            sms_destination="SIM-254700000001",
        )
        with self.assertRaisesRegex(RuntimeError, "immutability"):
            self.contacts.register(
                contact_binding_id="CONTACT-001", owner_id="CONTUID-001",
                sms_destination="SIM-254700000002",
            )


if __name__ == "__main__":
    unittest.main()
