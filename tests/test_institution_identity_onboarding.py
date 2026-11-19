"""R1-IOS-001: synthetic, fail-closed institutional registration conformance."""

from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from railone_crypto.key_provider import InMemoryEd25519KeyProvider, KeyPurpose
from railone_crypto.signature_service import ArtifactType, SignatureEnvelope, SignatureService
from railone_institutions.identity import (
    IdentityAdmissionState, InMemoryInstitutionIdentityRepository,
    InstitutionApplication, InstitutionClass, InstitutionOnboardingService,
)


class InstitutionOnboardingTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 19, 9, 0, tzinfo=timezone.utc)
        self.keys = InMemoryEd25519KeyProvider()
        for key_id, owner, purpose in (
            ("r1-onboarding", "RAILONE", KeyPurpose.INSTITUTION_ONBOARDING_SIGNING),
            ("partner-onboarding", "INST-PARTNER", KeyPurpose.INSTITUTION_ONBOARDING_SIGNING),
            ("wrong-purpose", "RAILONE", KeyPurpose.IDENTITY_SIGNING),
        ):
            self.keys.generate(key_id=key_id, owner_id=owner, purpose=purpose,
                               not_before=self.now - timedelta(days=1),
                               not_after=self.now + timedelta(days=400))
        self.signatures = SignatureService(self.keys)
        self.store = InMemoryInstitutionIdentityRepository()
        self.service = InstitutionOnboardingService(repository=self.store, signatures=self.signatures)
        self.app = InstitutionApplication(
            legal_name="SavannaPay Processing Ltd", display_name="SavannaPay",
            institution_class=InstitutionClass.PSP, home_jurisdiction="KE",
            registration_reference="SYN-KE-REG-001",
            regulatory_evidence_refs=("EVID-REG-01", "EVID-LICENSE-01"),
        )
        self.record = self.service.register(self.app, at=self.now)

    def decision(self, *, key="r1-onboarding", **updates):
        core = {
            "version": 1,
            "institution_id": self.record.institution_id,
            "application_sha256": self.app.fingerprint,
            "decision": "LEGAL_AND_REGULATORY_VERIFIED",
            "evidence_ref": "DUE-DILIGENCE-001",
            "evidence_sha256": "a" * 64,
            "expires_at": int((self.now + timedelta(days=30)).timestamp()),
        }
        core.update(updates)
        return self.signatures.sign_artifact(
            artifact_type=ArtifactType.INSTITUTION_ONBOARDING_ATTESTATION,
            payload=core, key_id=key, issued_at=self.now + timedelta(seconds=2),
        )

    def test_identity_is_distinct_and_pending_by_default(self):
        self.assertRegex(self.record.institution_id, r"^INST-KE-PSP-[A-Z2-7]{16}$")
        self.assertEqual(self.record.status, IdentityAdmissionState.PENDING_VERIFICATION)
        self.assertIsNone(self.record.signed_verification)
        with self.assertRaises(PermissionError):
            self.service.require_verified(self.record.institution_id, at=self.now)

    def test_trusted_signed_decision_verifies_but_does_not_create_partner_permission(self):
        self.service.verify(self.record.institution_id, self.decision(), at=self.now + timedelta(seconds=3))
        stored = self.service.require_verified(self.record.institution_id, at=self.now + timedelta(seconds=4))
        self.assertEqual(stored.application.fingerprint, self.app.fingerprint)
        self.assertEqual(stored.status, IdentityAdmissionState.VERIFIED)
        self.assertEqual(self.store.find_registration("KE", self.app.registration_reference), stored)
        self.assertFalse(hasattr(stored, "adapter_id"))
        self.assertFalse(hasattr(stored, "network_activated"))
        self.assertFalse(hasattr(stored, "continuity_uid"))

    def test_duplicate_natural_key_denied(self):
        with self.assertRaises(ValueError):
            self.service.register(self.app, at=self.now)
        with self.assertRaises(ValueError):
            self.service.register(replace(self.app, display_name="SavannaPay 2"), at=self.now)

    def test_invalid_registration_claims_denied(self):
        for app in (
            lambda: replace(self.app, home_jurisdiction="ke"),
            lambda: replace(self.app, regulatory_evidence_refs=()),
            lambda: replace(self.app, registration_reference="private raw account"),
            lambda: replace(self.app, institution_class="HUMAN"),
            lambda: replace(self.app, regulatory_evidence_refs=("EV-1", "EV-1")),
        ):
            with self.subTest(app=app), self.assertRaises(ValueError):
                app()

    def test_partner_cannot_sign_its_own_admission(self):
        with self.assertRaises(PermissionError):
            self.service.verify(self.record.institution_id, self.decision(key="partner-onboarding"),
                                at=self.now + timedelta(seconds=3))

    def test_wrong_purpose_key_cannot_sign_onboarding_decision(self):
        with self.assertRaises(PermissionError):
            self.decision(key="wrong-purpose")

    def test_tampered_signed_decision_is_denied(self):
        signed = self.decision().to_dict()
        signed["payload"]["decision"] = "LEGAL_AND_REGULATORY_VERIFIED_NEW"
        with self.assertRaises(PermissionError):
            self.service.verify(self.record.institution_id, SignatureEnvelope.from_dict(signed),
                                at=self.now + timedelta(seconds=3))

    def test_wrong_identity_or_registration_digest_is_denied(self):
        for update in ({"institution_id": "INST-KE-PSP-AAAAAAAAAAAAAAAA"},
                       {"application_sha256": "0" * 64},
                       {"decision": "APPROVED"},
                       {"evidence_sha256": "private"},
                       {"extra": "not allowed"}):
            with self.subTest(update=update), self.assertRaises(PermissionError):
                self.service.verify(self.record.institution_id, self.decision(**update),
                                    at=self.now + timedelta(seconds=3))

    def test_expiry_and_time_restrictions(self):
        with self.assertRaises(PermissionError):
            self.service.verify(self.record.institution_id,
                                self.decision(expires_at=int(self.now.timestamp()) + 2),
                                at=self.now + timedelta(seconds=3))
        with self.assertRaises(PermissionError):
            self.service.verify(self.record.institution_id,
                                self.decision(expires_at=int((self.now + timedelta(days=400)).timestamp())),
                                at=self.now + timedelta(seconds=3))
        with self.assertRaises(ValueError):
            self.service.verify(self.record.institution_id, self.decision(), at=self.now.replace(tzinfo=None))
        self.service.verify(self.record.institution_id, self.decision(), at=self.now + timedelta(seconds=3))
        with self.assertRaises(PermissionError):
            self.service.require_verified(self.record.institution_id, at=self.now + timedelta(days=31))

    def test_duplicate_verification_and_revoked_key_denied(self):
        self.service.verify(self.record.institution_id, self.decision(), at=self.now + timedelta(seconds=3))
        with self.assertRaises(PermissionError):
            self.service.verify(self.record.institution_id, self.decision(), at=self.now + timedelta(seconds=4))
        self.keys.revoke("r1-onboarding", reason="synthetic compromised key",
                         revoked_at=self.now + timedelta(seconds=5))
        with self.assertRaises(PermissionError):
            self.service.require_verified(self.record.institution_id, at=self.now + timedelta(seconds=6))

    def test_invalid_id_provenance_and_forged_store_registration_denied(self):
        from railone_institutions.identity import InstitutionIdentityRecord
        with self.assertRaises(ValueError):
            InstitutionIdentityRecord("INST-CA-PSP-AAAAAAAAAAAAAAAA", self.app,
                                      IdentityAdmissionState.PENDING_VERIFICATION, self.now)
        with self.assertRaises(PermissionError):
            self.store.insert(replace(self.record, status=IdentityAdmissionState.VERIFIED,
                                      signed_verification=self.decision(), verified_at=self.now))


if __name__ == "__main__":
    unittest.main()
