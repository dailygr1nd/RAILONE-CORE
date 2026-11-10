"""Regressions protecting sensitive metadata and dispatch boundaries."""
from __future__ import annotations

import hashlib
import unittest
from datetime import timedelta

from railone_security import (
    EncryptedAccountEndpointVault, EncryptedContactBindingVault,
    EncryptedProviderCredentialVault, InMemoryEncryptedSecretStore,
)
from railone_sandbox.metrics import MetricsRegistry
from tests.test_envelope_encryption import encryption_fixture
from tests import test_institution_admission_gateway as admission_tests


class VaultMetadataSecurityTests(unittest.TestCase):
    def test_no_cleartext_fingerprint_is_persisted_for_any_vault_kind(self):
        _, _, encryption = encryption_fixture()
        store = InMemoryEncryptedSecretStore()
        cases = (
            (EncryptedAccountEndpointVault(encryption=encryption, store=store),
             dict(institution_id="BANK-001", account_binding_id="acct-1",
                  provider_reference="254700000111"), "ACCOUNT_ENDPOINT", "BANK-001:acct-1"),
            (EncryptedContactBindingVault(encryption=encryption, store=store),
             dict(contact_binding_id="contact-1", owner_id="owner-1",
                  sms_destination="254700000112"), "CONTACT_DESTINATION", "contact-1"),
            (EncryptedProviderCredentialVault(encryption=encryption, store=store),
             dict(provider_id="BANK-001", credential_name="secret",
                  secret="sensitive-token"), "PROVIDER_CREDENTIAL", "BANK-001:secret"),
        )
        for vault, kwargs, name, record_id in cases:
            vault.register(**kwargs)
            record = store.require(vault_name=name, record_id=record_id)
            self.assertFalse(hasattr(record, "plaintext_sha256"))
            self.assertTrue(record.envelope.ciphertext)
            for cleartext in ("254700000111", "254700000112", "sensitive-token"):
                self.assertNotIn(hashlib.sha256(cleartext.encode()).hexdigest(), repr(record))

    def test_plaintext_hash_column_removed_only_in_forward_migration(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        text = (root / "migrations/0014_drop_plaintext_secret_fingerprints.sql").read_text()
        self.assertIn("DROP COLUMN plaintext_sha256", text)
        self.assertIn("ALTER TABLE railone.encrypted_secrets", text)


class SafeMetricLabelTests(unittest.TestCase):
    def test_trusted_bounded_labels_still_work(self):
        metrics = MetricsRegistry()
        metrics.increment("railone_sandbox_submissions_total", provider="BANK-KE",
                          outcome="ACCEPTED", scenario="SUCCESS")
        self.assertEqual(sum(metrics.snapshot().values()), 1)

    def test_rejects_raw_account_ids_unapproved_metric_labels(self):
        metrics = MetricsRegistry()
        for labels in (
            {"account_number": "123456789"},
            {"provider": "254700000111"},
            {"provider": "BANK-KE", "utt_id": "UTT-ABC"},
        ):
            with self.subTest(labels=labels), self.assertRaises(ValueError):
                metrics.increment("railone_sandbox_effects_total", **labels)
        self.assertEqual(metrics.snapshot(), {})

    def test_series_budget_is_bounded(self):
        with self.assertRaises(ValueError):
            MetricsRegistry(max_series=0)
        metrics = MetricsRegistry(max_series=1)
        metrics.increment("railone_sandbox_effects_total", provider="BANK-KE",
                          effect_type="SETTLED")
        with self.assertRaises(ValueError):
            metrics.increment("railone_sandbox_effects_total", provider="MPESA-KE",
                              effect_type="SETTLED")


class WorkerErrorRedactionTests(unittest.TestCase):
    def test_supervisor_does_not_publish_exception_payload(self):
        from railone_sandbox.workers import WorkerSupervisor
        class FailingWorker:
            def run_once(self):
                raise RuntimeError("PASSWORD=highly-sensitive-provider-secret")
        supervisor = WorkerSupervisor(FailingWorker(), failure_threshold=1)
        self.assertEqual(supervisor.tick(), ())
        self.assertEqual(supervisor.status().last_error, "RuntimeError")


class PreflightSecurityTests(unittest.TestCase):
    def test_denied_preflight_performs_no_account_decryption_or_preparation(self):
        from tests.test_provider_operations import ProviderOperationsTests
        from railone_operations import ProviderSubmissionCoordinator

        fixture = ProviderOperationsTests("test_preparation_is_idempotent_and_uses_stable_provider_key")
        fixture.setUp()
        class AuditResolver:
            calls = 0
            def resolve(self, *, institution_id, account_binding_id):
                self.calls += 1
                raise AssertionError("account endpoint must not be resolved")
        class RejectGate:
            def preflight(self, *, rtt_id, at):
                raise PermissionError("no independent fence authorization")
            def admit(self, request, *, at):
                raise AssertionError("admit must not run")
        resolver = AuditResolver()
        coordinator = ProviderSubmissionCoordinator(
            signatures=fixture.signatures, contracts=fixture.contracts,
            executions=fixture.executions, operations=fixture.operations,
            endpoint_resolver=resolver, event_signing_key_id="R1CORE:execution:2026-01",
            dispatch_mode="INSTITUTIONAL_SANDBOX", institutional_admission=RejectGate(),
        )
        with self.assertRaises(PermissionError):
            coordinator.dispatch(rtt_id=fixture.rtt_id, at=fixture.now + timedelta(seconds=22))
        self.assertEqual(resolver.calls, 0)
        with self.assertRaises(LookupError):
            fixture.operations.require_submission(fixture.rtt_id)

    def test_expired_wrapper_rejected_preflight_without_raw_endpoint_access(self):
        fixture = admission_tests.InstitutionalAdmissionGatewayTests("test_signed_wrapper_and_verified_adapter_are_admitted")
        fixture.setUp()
        with self.assertRaises(PermissionError):
            fixture.gateway.preflight(rtt_id=fixture.request.rtt_id,
                                      at=admission_tests.NOW + timedelta(seconds=61))
        self.assertEqual(fixture.fence.calls, 0)

    def test_wrong_fence_rejected_preflight(self):
        fixture = admission_tests.InstitutionalAdmissionGatewayTests("test_signed_wrapper_and_verified_adapter_are_admitted")
        fixture.setUp()
        fixture.fence.epoch += 1
        with self.assertRaises(PermissionError):
            fixture.gateway.preflight(rtt_id=fixture.request.rtt_id, at=admission_tests.NOW)


if __name__ == "__main__":
    unittest.main()
