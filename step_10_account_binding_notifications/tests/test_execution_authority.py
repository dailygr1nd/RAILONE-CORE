from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from railone_authority import ExecutionAuthorityService, ReceiverParticipationMode
from railone_crypto.key_provider import InMemoryEd25519KeyProvider, KeyPurpose
from railone_crypto.signature_service import (
    ArtifactType,
    SignatureEnvelope,
    SignatureService,
)


class ExecutionAuthorityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 7, 14, 11, 0, tzinfo=timezone.utc)
        self.keys = InMemoryEd25519KeyProvider()
        self.keys.generate(
            key_id="R1CORE:execution:2026-01",
            owner_id="R1CORE",
            purpose=KeyPurpose.EXECUTION_SIGNING,
            not_before=self.now - timedelta(days=1),
            not_after=self.now + timedelta(days=90),
        )
        self.signatures = SignatureService(self.keys)
        self.authority = ExecutionAuthorityService(self.signatures)

    def _sender(self):
        return self.authority.issue_sender_authority(
            utt_id="UTT-001",
            quote_id="Q-001",
            sender_actor_type="MERCHANT",
            sender_reference="MER002",
            amount_minor=250000,
            currency="KES",
            origin_context={
                "origin_system": "AVIA",
                "origin_intent_id": "AVIA-SUPPLIER-001",
                "merchant_id": "MER002",
                "purpose": "SUPPLIER_PAYMENT",
            },
            authorization_method="MERCHANT_ACTOR_ATTESTATION",
            authorization_reference="AUTH-001",
            signing_key_id="R1CORE:execution:2026-01",
            authorized_at=self.now,
            expires_at=self.now + timedelta(minutes=10),
        )

    def test_sender_authority_is_signed_and_utt_bound(self) -> None:
        sender = self._sender()
        result = self.signatures.verify_artifact(
            sender, expected_artifact_type=ArtifactType.ETK_S
        )

        self.assertTrue(result.valid)
        self.assertEqual(sender.payload["utt_id"], "UTT-001")
        self.assertEqual(sender.payload["quote_id"], "Q-001")
        self.assertEqual(sender.payload["amount_minor"], 250000)
        self.assertEqual(sender.payload["custody_model"], "NON_CUSTODIAL")

    def test_sender_authority_tampering_is_rejected(self) -> None:
        sender = self._sender()
        tampered = SignatureEnvelope(
            protected=sender.protected,
            payload={**sender.payload, "amount_minor": 1},
            signature=sender.signature,
        )

        with self.assertRaisesRegex(PermissionError, "PAYLOAD_HASH_MISMATCH"):
            self.authority.issue_receiver_participation(
                sender_authority=tampered,
                receiver_actor_type="SUPPLIER",
                receiver_reference="SUP-001",
                participation_mode=ReceiverParticipationMode.BENEFICIARY_PREAUTHORIZED,
                evidence_reference="BENEFICIARY-REG-001",
                signing_key_id="R1CORE:execution:2026-01",
                attested_at=self.now + timedelta(minutes=1),
                expires_at=self.now + timedelta(minutes=9),
            )

    def test_active_acceptance_marks_receiver_confirmed(self) -> None:
        receiver = self.authority.issue_receiver_participation(
            sender_authority=self._sender(),
            receiver_actor_type="PERSON",
            receiver_reference="RIO-RECEIVER",
            participation_mode=ReceiverParticipationMode.ACTIVE_ACCEPTANCE,
            evidence_reference="RECEIVER-AUTH-001",
            signing_key_id="R1CORE:execution:2026-01",
            attested_at=self.now + timedelta(minutes=1),
            expires_at=self.now + timedelta(minutes=9),
        )

        self.assertTrue(receiver.payload["receiver_confirmed"])
        self.assertEqual(receiver.payload["utt_id"], "UTT-001")
        self.assertTrue(
            self.signatures.verify_artifact(
                receiver, expected_artifact_type=ArtifactType.ETK_R
            ).valid
        )

    def test_passive_credit_does_not_claim_receiver_confirmation(self) -> None:
        receiver = self.authority.issue_receiver_participation(
            sender_authority=self._sender(),
            receiver_actor_type="SUPPLIER",
            receiver_reference="SUP-001",
            participation_mode=ReceiverParticipationMode.PASSIVE_CREDIT,
            evidence_reference="DIRECTORY-RESOLUTION-001",
            signing_key_id="R1CORE:execution:2026-01",
            attested_at=self.now + timedelta(minutes=1),
            expires_at=self.now + timedelta(minutes=9),
        )

        self.assertFalse(receiver.payload["receiver_confirmed"])

    def test_receiver_authority_cannot_outlive_sender_authority(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot outlive"):
            self.authority.issue_receiver_participation(
                sender_authority=self._sender(),
                receiver_actor_type="SUPPLIER",
                receiver_reference="SUP-001",
                participation_mode=ReceiverParticipationMode.BENEFICIARY_PREAUTHORIZED,
                evidence_reference="BENEFICIARY-REG-001",
                signing_key_id="R1CORE:execution:2026-01",
                attested_at=self.now + timedelta(minutes=1),
                expires_at=self.now + timedelta(minutes=11),
            )


if __name__ == "__main__":
    unittest.main()
