from __future__ import annotations

import hashlib
import unittest
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from railone_authority import ExecutionAuthorityService
from railone_contracts import (
    AccountRole,
    ActorReference,
    ContextType,
    InMemoryContractStore,
    OriginContext,
    PaymentPurpose,
    QuoteAcceptanceCommand,
    QuoteAcceptanceService,
    QuoteService,
    QuoteTerms,
)
from tests.support import endpoint, quote_service
from railone_crypto.key_provider import InMemoryEd25519KeyProvider, KeyPurpose
from railone_crypto.signature_service import ArtifactType, SignatureService
from railone_history import (
    READ_ANY_PERMISSION,
    AccessOutcome,
    InMemoryTransactionHistoryStore,
    SubjectKind,
    TransactionAccessDeniedError,
    TransactionHistoryService,
    TransactionReadContext,
    TransactionRole,
    UttTransactionIndexer,
)
from railone_identity import (
    IdentityAttestationVerifier,
    IdentityContinuityService,
    IdentitySeed,
    InMemoryContinuitySecretProvider,
    InMemoryIdentityRepository,
)


class ContinuityTransactionHistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 7, 14, 14, 0, tzinfo=timezone.utc)
        keys = InMemoryEd25519KeyProvider()
        for key_id, owner_id, purpose in (
            ("KYC-KE:identity:2026-01", "KYC-KE", KeyPurpose.IDENTITY_SIGNING),
            ("R1CORE:quote:2026-01", "R1CORE", KeyPurpose.QUOTE_SIGNING),
            ("R1CORE:execution:2026-01", "R1CORE", KeyPurpose.EXECUTION_SIGNING),
        ):
            keys.generate(
                key_id=key_id,
                owner_id=owner_id,
                purpose=purpose,
                not_before=self.now - timedelta(days=1),
                not_after=self.now + timedelta(days=90),
            )
        self.signatures = SignatureService(keys)
        secrets = InMemoryContinuitySecretProvider()
        secrets.register("continuity:v1", b"h" * 32)
        self.identities = InMemoryIdentityRepository()
        self.identity_service = IdentityContinuityService(
            continuity_key_id="continuity:v1",
            secrets=secrets,
            attestations=IdentityAttestationVerifier(self.signatures),
            repository=self.identities,
        )
        self.sender_uid = self._onboard("sender-subject", "ATT-SENDER")
        self.receiver_uid = self._onboard("receiver-subject", "ATT-RECEIVER")
        self.other_uid = self._onboard("other-subject", "ATT-OTHER")

        self.contracts = InMemoryContractStore()
        self.acceptance = QuoteAcceptanceService(
            signatures=self.signatures,
            authority=ExecutionAuthorityService(self.signatures),
            store=self.contracts,
            utt_signing_key_id="R1CORE:execution:2026-01",
            authority_signing_key_id="R1CORE:execution:2026-01",
        )
        self.history_store = InMemoryTransactionHistoryStore()
        self.indexer = UttTransactionIndexer(
            signatures=self.signatures,
            contracts=self.contracts,
            identities=self.identities,
            history=self.history_store,
        )
        self.history = TransactionHistoryService(self.history_store)

    def _onboard(self, subject: str, attestation_id: str) -> str:
        attestation = self.signatures.sign_artifact(
            artifact_type=ArtifactType.IDENTITY_ATTESTATION,
            payload={
                "attestation_id": attestation_id,
                "provider_id": "KYC-KE",
                "provider_subject_reference": subject,
                "verification_reference": f"VERIFY-{attestation_id}",
                "country_code": "KE",
                "verification_result": "VERIFIED",
                "trust_tier": "T2",
                "evidence_sha256": hashlib.sha256(subject.encode()).hexdigest(),
                "issued_at": int(self.now.timestamp()),
                "expires_at": int((self.now + timedelta(hours=1)).timestamp()),
            },
            key_id="KYC-KE:identity:2026-01",
            issued_at=self.now,
        )
        result = self.identity_service.onboard(
            seed=IdentitySeed(
                provider_id="KYC-KE",
                provider_subject_reference=subject,
                country_code="KE",
            ),
            attestation=attestation,
            corridor="EA",
            at=self.now,
        )
        return result.bundle.identity.continuity_uid

    def _p2p_utt(self, *, request_id: str = "REQ-P2P-001") -> str:
        quote = quote_service(self.signatures).issue_quote(
            terms=QuoteTerms(
                request_id=request_id,
                payer=ActorReference(
                    "PERSON", self.sender_uid, endpoint("BIND-PAYER-P2P", AccountRole.DEBIT)
                ),
                beneficiary=ActorReference(
                    "PERSON", self.receiver_uid, endpoint("BIND-BEN-P2P", AccountRole.CREDIT)
                ),
                purpose=PaymentPurpose.PERSON_TO_PERSON,
                amount_minor=100_000,
                currency_from="KES",
                receive_amount_minor=99_500,
                currency_to="KES",
                total_fee_minor=500,
                routing_budget_minor=200,
                fx_rate="1.000000",
                corridor_id="KE-DOMESTIC",
                service_level="STANDARD",
                routing_policy_id="POLICY-KE-P2P",
                pricing_version="2026-07",
            ),
            signing_key_id="R1CORE:quote:2026-01",
            issued_at=self.now,
            expires_at=self.now + timedelta(minutes=1),
        )
        result = self.acceptance.accept(
            QuoteAcceptanceCommand(
                signed_quote=quote,
                origin=OriginContext(
                    origin_system="RAILONE_CLIENT",
                    origin_intent_id=request_id,
                    context_type=ContextType.P2P,
                    purpose=PaymentPurpose.PERSON_TO_PERSON,
                    continuity_uid=self.sender_uid,
                ),
                authorization_method="IDENTITY_SESSION_ATTESTATION",
                authorization_reference=f"AUTH-{request_id}",
                idempotency_key=f"IDEM-{request_id}",
            ),
            at=self.now + timedelta(seconds=10),
        )
        return result.contract.utt_id

    def _merchant_utt(self) -> str:
        quote = quote_service(self.signatures).issue_quote(
            terms=QuoteTerms(
                request_id="REQ-MERCHANT-001",
                payer=ActorReference(
                    "MERCHANT", "MER002", endpoint("BIND-MERCHANT", AccountRole.DEBIT)
                ),
                beneficiary=ActorReference(
                    "SUPPLIER", "SUP001", endpoint("BIND-SUPPLIER", AccountRole.CREDIT)
                ),
                purpose=PaymentPurpose.SUPPLIER_PAYMENT,
                amount_minor=250_000,
                currency_from="KES",
                receive_amount_minor=247_500,
                currency_to="KES",
                total_fee_minor=2_500,
                routing_budget_minor=1_000,
                fx_rate="1.000000",
                corridor_id="KE-DOMESTIC",
                service_level="STANDARD",
                routing_policy_id="POLICY-KE-MERCHANT",
                pricing_version="2026-07",
            ),
            signing_key_id="R1CORE:quote:2026-01",
            issued_at=self.now,
            expires_at=self.now + timedelta(minutes=1),
        )
        result = self.acceptance.accept(
            QuoteAcceptanceCommand(
                signed_quote=quote,
                origin=OriginContext(
                    origin_system="AVIA",
                    origin_intent_id="AVIA-SUPPLIER-001",
                    context_type=ContextType.MERCHANT,
                    purpose=PaymentPurpose.SUPPLIER_PAYMENT,
                    merchant_id="MER002",
                    branch_id="BR001",
                ),
                authorization_method="MERCHANT_ACTOR_ATTESTATION",
                authorization_reference="AUTH-MERCHANT-001",
                idempotency_key="IDEM-MERCHANT-001",
            ),
            at=self.now + timedelta(seconds=10),
        )
        return result.contract.utt_id

    def test_sender_and_receiver_can_view_same_utt_through_their_contuids(self) -> None:
        utt_id = self._p2p_utt()
        self.indexer.index(utt_id=utt_id, at=self.now + timedelta(seconds=11))

        sender_page = self.history.list_by_continuity_uid(
            continuity_uid=self.sender_uid,
            access=TransactionReadContext(
                principal_id="sender-session", continuity_uid=self.sender_uid
            ),
            at=self.now + timedelta(seconds=12),
        )
        receiver_page = self.history.list_by_continuity_uid(
            continuity_uid=self.receiver_uid,
            access=TransactionReadContext(
                principal_id="receiver-session", continuity_uid=self.receiver_uid
            ),
            at=self.now + timedelta(seconds=13),
        )

        self.assertEqual(sender_page.entries[0].transaction.utt_id, utt_id)
        self.assertIn(TransactionRole.PAYER, sender_page.entries[0].matched_roles)
        self.assertEqual(receiver_page.entries[0].transaction.utt_id, utt_id)
        self.assertEqual(
            receiver_page.entries[0].matched_roles,
            (TransactionRole.BENEFICIARY,),
        )

    def test_participant_can_lookup_transaction_by_utt(self) -> None:
        utt_id = self._p2p_utt()
        self.indexer.index(utt_id=utt_id, at=self.now + timedelta(seconds=11))

        entry = self.history.get_by_utt(
            utt_id=utt_id,
            access=TransactionReadContext(
                principal_id="receiver-session", continuity_uid=self.receiver_uid
            ),
            at=self.now + timedelta(seconds=12),
        )

        self.assertEqual(entry.transaction.utt_id, utt_id)
        self.assertEqual(entry.matched_roles, (TransactionRole.BENEFICIARY,))

    def test_unrelated_contuid_is_denied_and_attempt_is_audited(self) -> None:
        utt_id = self._p2p_utt()
        self.indexer.index(utt_id=utt_id, at=self.now + timedelta(seconds=11))

        with self.assertRaises(TransactionAccessDeniedError):
            self.history.get_by_utt(
                utt_id=utt_id,
                access=TransactionReadContext(
                    principal_id="other-session", continuity_uid=self.other_uid
                ),
                at=self.now + timedelta(seconds=12),
            )

        audit = self.history_store.audits()[-1]
        self.assertEqual(audit.outcome, AccessOutcome.DENIED)
        self.assertEqual(audit.target_id, utt_id)

    def test_privileged_lookup_requires_and_audits_a_reason(self) -> None:
        utt_id = self._p2p_utt()
        self.indexer.index(utt_id=utt_id, at=self.now + timedelta(seconds=11))
        without_reason = TransactionReadContext(
            principal_id="ops-001", permissions=(READ_ANY_PERMISSION,)
        )
        with self.assertRaisesRegex(TransactionAccessDeniedError, "requires an access reason"):
            self.history.get_by_utt(
                utt_id=utt_id,
                access=without_reason,
                at=self.now + timedelta(seconds=12),
            )

        entry = self.history.get_by_utt(
            utt_id=utt_id,
            access=TransactionReadContext(
                principal_id="ops-001",
                permissions=(READ_ANY_PERMISSION,),
                access_reason="PROVIDER_RECONCILIATION_CASE_001",
            ),
            at=self.now + timedelta(seconds=13),
        )

        self.assertEqual(entry.transaction.utt_id, utt_id)
        self.assertEqual(self.history_store.audits()[-1].outcome, AccessOutcome.ALLOWED)

    def test_projection_does_not_copy_account_references_or_raw_identity_seed(self) -> None:
        utt_id = self._p2p_utt()
        projection = self.indexer.index(
            utt_id=utt_id, at=self.now + timedelta(seconds=11)
        )

        stored = repr(asdict(projection))
        self.assertNotIn("PAYER-ACCOUNT", stored)
        self.assertNotIn("BENEFICIARY-ACCOUNT", stored)
        self.assertNotIn("sender-subject", stored)
        self.assertNotIn("receiver-subject", stored)

    def test_merchant_context_uses_merchant_and_branch_scopes_not_fake_contuid(self) -> None:
        utt_id = self._merchant_utt()
        self.indexer.index(utt_id=utt_id, at=self.now + timedelta(seconds=11))
        links = self.history_store.links_for_utt(utt_id)

        self.assertIn(SubjectKind.MERCHANT_ID, {link.subject_kind for link in links})
        self.assertIn(SubjectKind.BRANCH_ID, {link.subject_kind for link in links})
        self.assertNotIn(SubjectKind.CONTINUITY_UID, {link.subject_kind for link in links})
        entry = self.history.get_by_utt(
            utt_id=utt_id,
            access=TransactionReadContext(
                principal_id="avia-merchant-session", merchant_ids=("MER002",)
            ),
            at=self.now + timedelta(seconds=12),
        )
        self.assertEqual(entry.transaction.context_type, "MERCHANT")

    def test_reindexing_same_immutable_utt_is_idempotent(self) -> None:
        utt_id = self._p2p_utt()
        first = self.indexer.index(utt_id=utt_id, at=self.now + timedelta(seconds=11))
        second = self.indexer.index(utt_id=utt_id, at=self.now + timedelta(seconds=30))

        self.assertIs(first, second)
        self.assertEqual(len(self.history_store.links_for_utt(utt_id)), 2)


if __name__ == "__main__":
    unittest.main()
