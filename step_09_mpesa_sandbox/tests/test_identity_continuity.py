from __future__ import annotations

import hashlib
import unittest
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from railone_crypto.key_provider import InMemoryEd25519KeyProvider, KeyPurpose
from railone_crypto.signature_service import ArtifactType, SignatureService
from railone_identity.attestation import IdentityAttestationVerifier
from railone_identity import IdentityStatus
from railone_identity.continuity import (
    IdentityContinuityService,
    IdentitySeed,
    InMemoryContinuitySecretProvider,
    InMemoryIdentityRepository,
)


class IdentityContinuityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 7, 14, 10, 0, tzinfo=timezone.utc)
        self.keys = InMemoryEd25519KeyProvider()
        self.keys.generate(
            key_id="KYC-KE:identity:2026-01",
            owner_id="KYC-KE",
            purpose=KeyPurpose.IDENTITY_SIGNING,
            not_before=self.now - timedelta(days=1),
            not_after=self.now + timedelta(days=365),
        )
        self.signatures = SignatureService(self.keys)
        self.secrets = InMemoryContinuitySecretProvider()
        self.secrets.register("continuity:v1", b"c" * 32)
        self.repository = InMemoryIdentityRepository()
        self.service = IdentityContinuityService(
            continuity_key_id="continuity:v1",
            secrets=self.secrets,
            attestations=IdentityAttestationVerifier(self.signatures),
            repository=self.repository,
        )
        self.seed = IdentitySeed(
            provider_id="KYC-KE",
            provider_subject_reference="provider-subject-001",
            country_code="KE",
        )

    def _attestation(
        self,
        *,
        expires_in_seconds: int = 3600,
        attestation_id: str = "ATT-KYC-001",
        trust_tier: str = "T2",
    ):
        payload = {
            "attestation_id": attestation_id,
            "provider_id": "KYC-KE",
            "provider_subject_reference": "provider-subject-001",
            "verification_reference": "VERIFY-001",
            "country_code": "KE",
            "verification_result": "VERIFIED",
            "trust_tier": trust_tier,
            "evidence_sha256": hashlib.sha256(b"provider-evidence").hexdigest(),
            "issued_at": int(self.now.timestamp()),
            "expires_at": int(self.now.timestamp()) + expires_in_seconds,
        }
        return self.signatures.sign_artifact(
            artifact_type=ArtifactType.IDENTITY_ATTESTATION,
            payload=payload,
            key_id="KYC-KE:identity:2026-01",
            issued_at=self.now,
        )

    def test_same_verified_subject_resolves_same_identity(self) -> None:
        first = self.service.onboard(
            seed=self.seed,
            attestation=self._attestation(),
            corridor="EA",
            at=self.now,
        )
        second = self.service.onboard(
            seed=self.seed,
            attestation=self._attestation(),
            corridor="EA",
            at=self.now,
        )

        self.assertFalse(first.existing)
        self.assertTrue(second.existing)
        self.assertEqual(
            first.bundle.identity.continuity_uid,
            second.bundle.identity.continuity_uid,
        )
        self.assertEqual(len(first.bundle.identity.continuity_uid), 37)

    def test_identity_objects_do_not_store_provider_subject_reference(self) -> None:
        result = self.service.onboard(
            seed=self.seed,
            attestation=self._attestation(),
            corridor="EA",
            at=self.now,
        )

        stored = repr(asdict(result.bundle))
        self.assertNotIn("provider-subject-001", stored)

    def test_expired_attestation_is_rejected(self) -> None:
        with self.assertRaisesRegex(PermissionError, "ATTESTATION_EXPIRED"):
            self.service.onboard(
                seed=self.seed,
                attestation=self._attestation(expires_in_seconds=60),
                corridor="EA",
                at=self.now + timedelta(minutes=2),
            )

    def test_subject_mismatch_is_rejected(self) -> None:
        other_seed = IdentitySeed(
            provider_id="KYC-KE",
            provider_subject_reference="different-subject",
            country_code="KE",
        )
        with self.assertRaisesRegex(PermissionError, "subject mismatch"):
            self.service.onboard(
                seed=other_seed,
                attestation=self._attestation(),
                corridor="EA",
                at=self.now,
            )

    def test_identity_is_resolvable_by_continuity_uid(self) -> None:
        created = self.service.onboard(
            seed=self.seed,
            attestation=self._attestation(),
            corridor="EA",
            at=self.now,
        ).bundle

        resolved = self.service.get(created.identity.continuity_uid)

        self.assertEqual(resolved.genesis, created.genesis)
        self.assertEqual(resolved.identity.railone_id, created.identity.railone_id)

    def test_revision_appends_riv_without_mutating_genesis_or_public_id(self) -> None:
        original = self.service.onboard(
            seed=self.seed,
            attestation=self._attestation(),
            corridor="EA",
            at=self.now,
        ).bundle

        updated = self.service.revise(
            seed=self.seed,
            attestation=self._attestation(
                attestation_id="ATT-KYC-002", trust_tier="T3"
            ),
            status=IdentityStatus.REVERIFICATION_REQUIRED,
            reason="PERIODIC_REVERIFICATION",
            at=self.now + timedelta(minutes=5),
        )

        self.assertIs(updated.genesis, original.genesis)
        self.assertEqual(updated.identity.railone_id, original.identity.railone_id)
        self.assertEqual(updated.identity.continuity_uid, original.identity.continuity_uid)
        self.assertEqual(updated.active_revision.revision, 2)
        self.assertEqual(updated.active_revision.trust_tier.value, "T3")
        self.assertEqual(
            updated.active_revision.status, IdentityStatus.REVERIFICATION_REQUIRED
        )
        self.assertEqual(updated.identity.status, IdentityStatus.REVERIFICATION_REQUIRED)
        history = self.service.history(original.identity.continuity_uid)
        self.assertEqual(tuple(revision.revision for revision in history), (1, 2))
        self.assertEqual(history[0].trust_tier.value, "T2")

    def test_attestation_cannot_be_reused_for_another_revision(self) -> None:
        original = self.service.onboard(
            seed=self.seed,
            attestation=self._attestation(),
            corridor="EA",
            at=self.now,
        ).bundle
        with self.assertRaisesRegex(ValueError, "attestation was already used"):
            self.service.revise(
                seed=self.seed,
                attestation=self._attestation(),
                status=IdentityStatus.SUSPENDED,
                reason="RISK_REVIEW",
                at=self.now + timedelta(minutes=5),
            )
        self.assertEqual(self.service.get(original.identity.continuity_uid), original)


if __name__ == "__main__":
    unittest.main()
