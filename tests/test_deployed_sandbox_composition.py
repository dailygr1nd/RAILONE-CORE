from __future__ import annotations

import unittest
from pathlib import Path

from railone_sandbox.deployment import (
    DeployedSandboxConfig, compose_deployed_sandbox,
)


class NoopKeyClient:
    def wrap(self, *, key_id, plaintext, context):
        raise AssertionError("composition must not access keys")

    def unwrap(self, *, key_id, ciphertext, context):
        raise AssertionError("composition must not access keys")


class NoopConsumer:
    def apply(self, effect):
        pass


class DeployedSandboxCompositionTests(unittest.TestCase):
    def test_configuration_requires_simulation_mode_and_all_key_ids(self):
        root = Path(__file__).resolve().parents[1]
        incomplete = DeployedSandboxConfig(
            database_url="postgresql://synthetic", migrations_directory=root / "migrations",
            account_endpoint_key_id="", contact_destination_key_id="contact-v1",
            provider_credential_key_id="credential-v1",
            notification_body_key_id="notification-v1", worker_id="worker-1",
        )
        with self.assertRaisesRegex(ValueError, "account_endpoint_key_id"):
            incomplete.validate()

    def test_composition_builds_durable_encrypted_boundaries_without_loading_keys(self):
        root = Path(__file__).resolve().parents[1]
        config = DeployedSandboxConfig(
            database_url="postgresql://synthetic", migrations_directory=root / "migrations",
            account_endpoint_key_id="account-v1",
            contact_destination_key_id="contact-v1",
            provider_credential_key_id="credential-v1",
            notification_body_key_id="notification-v1",
            worker_id="sandbox-worker-1",
        )
        runtime = compose_deployed_sandbox(
            config=config, key_client=NoopKeyClient(),
            effect_consumer=NoopConsumer(), connection_factory=lambda: None,
        )
        self.assertEqual(runtime.config.runtime_mode, "SIMULATED_PILOT")
        self.assertEqual(runtime.bank_adapter.provider_id, "BANK-KE")
        self.assertEqual(runtime.mpesa_adapter.provider_id, "MPESA-KE")
        self.assertEqual(runtime.readiness()["status"], "NOT_READY")


if __name__ == "__main__":
    unittest.main()
