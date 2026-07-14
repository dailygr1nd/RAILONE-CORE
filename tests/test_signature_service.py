from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from railone_crypto.canonical_json import (
    CanonicalizationError,
    canonical_json_bytes,
)
from railone_crypto.key_provider import InMemoryEd25519KeyProvider, KeyPurpose
from railone_crypto.signature_service import (
    ArtifactType,
    SignatureEnvelope,
    SignatureService,
)


class SignatureServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 7, 14, 9, 0, tzinfo=timezone.utc)
        self.keys = InMemoryEd25519KeyProvider()
        self.keys.generate(
            key_id="R1CORE:execution:2026-01",
            owner_id="R1CORE",
            purpose=KeyPurpose.EXECUTION_SIGNING,
            not_before=self.now - timedelta(days=1),
            not_after=self.now + timedelta(days=90),
        )
        self.keys.generate(
            key_id="R1CORE:quote:2026-01",
            owner_id="R1CORE",
            purpose=KeyPurpose.QUOTE_SIGNING,
            not_before=self.now - timedelta(days=1),
            not_after=self.now + timedelta(days=90),
        )
        self.signatures = SignatureService(self.keys)
        self.utt = {
            "utt_id": "UTT-01J2EXAMPLE",
            "quote_id": "Q-01J2EXAMPLE",
            "amount_minor": 250000,
            "currency": "KES",
            "pricing_model": "PER_INTENT",
            "custody_model": "NON_CUSTODIAL",
        }

    def test_signs_and_verifies_utt(self) -> None:
        envelope = self.signatures.sign_artifact(
            artifact_type=ArtifactType.UTT,
            payload=self.utt,
            key_id="R1CORE:execution:2026-01",
            issued_at=self.now,
        )

        result = self.signatures.verify_artifact(
            envelope, expected_artifact_type=ArtifactType.UTT
        )

        self.assertTrue(result.valid)
        self.assertEqual(result.reason, "VALID")

    def test_ed25519_signature_is_deterministic_for_same_input(self) -> None:
        first = self.signatures.sign_artifact(
            artifact_type=ArtifactType.UTT,
            payload=self.utt,
            key_id="R1CORE:execution:2026-01",
            issued_at=self.now,
        )
        second = self.signatures.sign_artifact(
            artifact_type=ArtifactType.UTT,
            payload=self.utt,
            key_id="R1CORE:execution:2026-01",
            issued_at=self.now,
        )

        self.assertEqual(first.signature, second.signature)

    def test_payload_tampering_is_rejected(self) -> None:
        envelope = self.signatures.sign_artifact(
            artifact_type=ArtifactType.UTT,
            payload=self.utt,
            key_id="R1CORE:execution:2026-01",
            issued_at=self.now,
        )
        tampered = SignatureEnvelope(
            protected=envelope.protected,
            payload={**envelope.payload, "amount_minor": 999999},
            signature=envelope.signature,
        )

        result = self.signatures.verify_artifact(tampered)

        self.assertFalse(result.valid)
        self.assertEqual(result.reason, "PAYLOAD_HASH_MISMATCH")

    def test_wrong_artifact_type_is_rejected(self) -> None:
        envelope = self.signatures.sign_artifact(
            artifact_type=ArtifactType.UTT,
            payload=self.utt,
            key_id="R1CORE:execution:2026-01",
            issued_at=self.now,
        )

        result = self.signatures.verify_artifact(
            envelope, expected_artifact_type=ArtifactType.RTT
        )

        self.assertFalse(result.valid)
        self.assertEqual(result.reason, "ARTIFACT_TYPE_MISMATCH")

    def test_key_purpose_is_enforced_at_signing(self) -> None:
        with self.assertRaises(PermissionError):
            self.signatures.sign_artifact(
                artifact_type=ArtifactType.UTT,
                payload=self.utt,
                key_id="R1CORE:quote:2026-01",
                issued_at=self.now,
            )

    def test_revoked_key_is_rejected(self) -> None:
        envelope = self.signatures.sign_artifact(
            artifact_type=ArtifactType.UTT,
            payload=self.utt,
            key_id="R1CORE:execution:2026-01",
            issued_at=self.now,
        )
        self.keys.revoke(
            "R1CORE:execution:2026-01",
            reason="compromise drill",
            revoked_at=self.now + timedelta(minutes=1),
        )

        result = self.signatures.verify_artifact(envelope)

        self.assertFalse(result.valid)
        self.assertEqual(result.reason, "KEY_REVOKED")

    def test_signing_outside_key_window_is_rejected(self) -> None:
        with self.assertRaises(PermissionError):
            self.signatures.sign_artifact(
                artifact_type=ArtifactType.UTT,
                payload=self.utt,
                key_id="R1CORE:execution:2026-01",
                issued_at=self.now + timedelta(days=100),
            )

    def test_float_is_rejected_from_signed_financial_payload(self) -> None:
        with self.assertRaises(CanonicalizationError):
            canonical_json_bytes({"amount": 25.50, "currency": "KES"})


if __name__ == "__main__":
    unittest.main()
