from __future__ import annotations

import hashlib
import unittest
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from railone_crypto.key_provider import InMemoryEd25519KeyProvider, KeyPurpose
from railone_crypto.signature_service import ArtifactType, SignatureService
from railone_identity.attestation import IdentityAttestationVerifier
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

    def _attestation(self, *, expires_in_seconds: int = 3600):
        payload = {
            "attestation_id": "ATT-KYC-001",
            "provider_id": "KYC-KE",
            "provider_subject_reference": "provider-subject-001",
            "verification_reference": "VERIFY-001",
            "country_code": "KE",
            "verification_result": "VERIFIED",
            "trust_tier": "T2",
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


if __name__ == "__main__":
    unittest.main()
