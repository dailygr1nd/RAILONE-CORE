from __future__ import annotations

import hashlib
import unittest
from datetime import datetime, timedelta, timezone

from railone_crypto.canonical_json import canonical_json_bytes
from railone_crypto.key_provider import InMemoryEd25519KeyProvider, KeyPurpose
from railone_crypto.signature_service import ArtifactType, SignatureEnvelope, SignatureService
from railone_projection import (
    InMemoryProviderOutcomeProjectionStore,
    ProviderProgressState,
    SignedProviderOutcomeProjector,
)


class ProviderOutcomeProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 7, 14, 18, 0, tzinfo=timezone.utc)
        keys = InMemoryEd25519KeyProvider()
        keys.generate(
            key_id="R1CORE:execution:projection",
            owner_id="R1CORE",
            purpose=KeyPurpose.EXECUTION_SIGNING,
            not_before=self.now - timedelta(days=1),
            not_after=self.now + timedelta(days=30),
        )
        self.signatures = SignatureService(keys)
        self.store = InMemoryProviderOutcomeProjectionStore()
        self.projector = SignedProviderOutcomeProjector(
            signatures=self.signatures, store=self.store
        )

    def _event(self, *, version: int, event_type: str, code: str | None = None):
        core = {
            "event_type": event_type,
            "aggregate_type": "PROVIDER_SUBMISSION",
            "aggregate_id": "SUB-001",
            "utt_id": "UTT-" + "A" * 32,
            "rtt_id": "RTT-" + "B" * 32,
            "provider_id": "MPESA-KE",
            "submission_version": version,
            "data": {
                "outcome": "ACCEPTED" if code else None,
                "code": code,
                "external_reference": "MPS-001" if code else None,
                "rejection_disposition": None,
            },
            "occurred_at": int(self.now.timestamp()) + version,
        }
        event_id = "EVT-" + hashlib.sha256(
            canonical_json_bytes(core)
        ).hexdigest().upper()[:32]
        return self.signatures.sign_artifact(
            artifact_type=ArtifactType.EXECUTION_EVENT,
            payload={"event_id": event_id, **core},
            key_id="R1CORE:execution:projection",
            issued_at=self.now,
        )

    def test_signed_event_projects_provider_acceptance_without_claiming_settlement(self):
        event = self._event(
            version=3,
            event_type="PROVIDER_SUBMISSION_ACCEPTED",
            code="ACCEPTED_FOR_PROCESSING",
        )
        projection, applied = self.projector.project(event, at=self.now)

        self.assertTrue(applied)
        self.assertEqual(projection.state, ProviderProgressState.ACCEPTED_FOR_PROCESSING)
        self.assertNotEqual(projection.state.value, "SUCCEEDED")
        self.assertEqual(self.store.get("SUB-001"), projection)

    def test_duplicate_signed_event_is_consumed_exactly_once(self):
        event = self._event(version=1, event_type="PROVIDER_SUBMISSION_PREPARED")
        first, first_applied = self.projector.project(event, at=self.now)
        second, second_applied = self.projector.project(event, at=self.now)

        self.assertTrue(first_applied)
        self.assertFalse(second_applied)
        self.assertEqual(first, second)

    def test_late_older_event_cannot_regress_projection(self):
        accepted = self._event(
            version=3,
            event_type="PROVIDER_SUBMISSION_ACCEPTED",
            code="ACCEPTED_FOR_PROCESSING",
        )
        prepared = self._event(version=1, event_type="PROVIDER_SUBMISSION_PREPARED")
        self.projector.project(accepted, at=self.now)
        _, consumed = self.projector.project(prepared, at=self.now)

        self.assertTrue(consumed)
        current = self.store.get("SUB-001")
        self.assertEqual(current.submission_version, 3)
        self.assertEqual(current.state, ProviderProgressState.ACCEPTED_FOR_PROCESSING)

    def test_signed_event_with_false_content_identifier_is_rejected(self):
        valid = self._event(version=1, event_type="PROVIDER_SUBMISSION_PREPARED")
        payload = dict(valid.payload)
        payload["event_id"] = "EVT-" + "0" * 32
        resigned = self.signatures.sign_artifact(
            artifact_type=ArtifactType.EXECUTION_EVENT,
            payload=payload,
            key_id="R1CORE:execution:projection",
            issued_at=self.now,
        )
        with self.assertRaises(PermissionError):
            self.projector.project(resigned, at=self.now)

    def test_tampered_event_signature_is_rejected(self):
        valid = self._event(version=1, event_type="PROVIDER_SUBMISSION_PREPARED")
        payload = dict(valid.payload)
        payload["provider_id"] = "ATTACKER"
        tampered = SignatureEnvelope(valid.protected, payload, valid.signature)
        with self.assertRaises(PermissionError):
            self.projector.project(tampered, at=self.now)


if __name__ == "__main__":
    unittest.main()
