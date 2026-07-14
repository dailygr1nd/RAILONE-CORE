from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from railone_authority import ExecutionAuthorityService
from railone_contracts import (
    AccountRole,
    ActorReference,
    ContextType,
    IdempotencyConflictError,
    InMemoryContractStore,
    OriginContext,
    PaymentPurpose,
    QuoteAcceptanceCommand,
    QuoteAcceptanceService,
    QuoteAlreadyAcceptedError,
    QuoteService,
    QuoteTerms,
    UttNotFoundError,
)
from tests.support import endpoint, quote_service
from railone_crypto.key_provider import InMemoryEd25519KeyProvider, KeyPurpose
from railone_crypto.signature_service import ArtifactType, SignatureEnvelope, SignatureService


class QuoteAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)
        self.keys = InMemoryEd25519KeyProvider()
        self.keys.generate(
            key_id="R1CORE:quote:2026-01",
            owner_id="R1CORE",
            purpose=KeyPurpose.QUOTE_SIGNING,
            not_before=self.now - timedelta(days=1),
            not_after=self.now + timedelta(days=90),
        )
        self.keys.generate(
            key_id="R1CORE:execution:2026-01",
            owner_id="R1CORE",
            purpose=KeyPurpose.EXECUTION_SIGNING,
            not_before=self.now - timedelta(days=1),
            not_after=self.now + timedelta(days=90),
        )
        self.signatures = SignatureService(self.keys)
        self.quotes = quote_service(self.signatures)
        self.store = InMemoryContractStore()
        self.acceptance = QuoteAcceptanceService(
            signatures=self.signatures,
            authority=ExecutionAuthorityService(self.signatures),
            store=self.store,
            utt_signing_key_id="R1CORE:execution:2026-01",
            authority_signing_key_id="R1CORE:execution:2026-01",
        )
        self.terms = QuoteTerms(
            request_id="REQ-001",
            payer=ActorReference(
                "MERCHANT", "MER002", endpoint("BIND-PAYER-001", AccountRole.DEBIT)
            ),
            beneficiary=ActorReference(
                "SUPPLIER", "SUP-001", endpoint("BIND-BEN-001", AccountRole.CREDIT)
            ),
            purpose=PaymentPurpose.SUPPLIER_PAYMENT,
            amount_minor=250000,
            currency_from="KES",
            receive_amount_minor=247500,
            currency_to="KES",
            total_fee_minor=2500,
            routing_budget_minor=1000,
            fx_rate="1.000000",
            corridor_id="KE-DOMESTIC",
            service_level="STANDARD",
            routing_policy_id="POLICY-KE-01",
            pricing_version="2026-07",
            max_attempts=5,
        )
        self.origin = OriginContext(
            origin_system="AVIA",
            origin_intent_id="AVIA-SUPPLIER-001",
            context_type=ContextType.MERCHANT,
            purpose=PaymentPurpose.SUPPLIER_PAYMENT,
            merchant_id="MER002",
            branch_id="BR001",
        )

    def _quote(self):
        return self.quotes.issue_quote(
            terms=self.terms,
            signing_key_id="R1CORE:quote:2026-01",
            issued_at=self.now,
            expires_at=self.now + timedelta(seconds=60),
        )

    def _command(self, *, idempotency_key="idem-001", quote=None):
        return QuoteAcceptanceCommand(
            signed_quote=quote or self._quote(),
            origin=self.origin,
            authorization_method="MERCHANT_ACTOR_ATTESTATION",
            authorization_reference="AUTH-001",
            idempotency_key=idempotency_key,
        )

    def test_signed_quote_does_not_bind_a_specific_rail(self) -> None:
        quote = self._quote()
        self.assertTrue(
            self.signatures.verify_artifact(
                quote, expected_artifact_type=ArtifactType.QUOTE
            ).valid
        )
        self.assertNotIn("selected_route", quote.payload)
        self.assertNotIn("rail", quote.payload)

    def test_acceptance_creates_immutable_utt_and_bound_etk_s(self) -> None:
        result = self.acceptance.accept(self._command(), at=self.now + timedelta(seconds=10))
        contract = result.contract

        self.assertFalse(result.replayed)
        self.assertEqual(
            contract.signed_utt.payload["etk_s_id"],
            contract.sender_authority.payload["etk_s_id"],
        )
        self.assertEqual(contract.sender_authority.payload["utt_id"], contract.utt_id)
        self.assertEqual(contract.signed_utt.payload["pricing_model"], "PER_INTENT")
        self.assertEqual(contract.signed_utt.payload["custody_model"], "NON_CUSTODIAL")
        self.assertTrue(
            self.signatures.verify_artifact(
                contract.signed_utt, expected_artifact_type=ArtifactType.UTT
            ).valid
        )
        with self.assertRaises(TypeError):
            contract.signed_utt.payload["amount_minor"] = 1

    def test_identical_idempotent_replay_returns_original_contract(self) -> None:
        command = self._command()
        first = self.acceptance.accept(command, at=self.now + timedelta(seconds=10))
        second = self.acceptance.accept(command, at=self.now + timedelta(minutes=10))

        self.assertTrue(second.replayed)
        self.assertEqual(first.contract.utt_id, second.contract.utt_id)
        self.assertEqual(
            first.contract.signed_utt.signature,
            second.contract.signed_utt.signature,
        )

    def test_idempotency_key_reuse_with_different_material_is_rejected(self) -> None:
        self.acceptance.accept(self._command(), at=self.now + timedelta(seconds=10))
        changed_origin = OriginContext(
            origin_system="AVIA",
            origin_intent_id="DIFFERENT-INTENT",
            context_type=ContextType.MERCHANT,
            purpose=PaymentPurpose.SUPPLIER_PAYMENT,
            merchant_id="MER002",
        )
        changed = QuoteAcceptanceCommand(
            signed_quote=self._quote(),
            origin=changed_origin,
            authorization_method="MERCHANT_ACTOR_ATTESTATION",
            authorization_reference="AUTH-001",
            idempotency_key="idem-001",
        )

        with self.assertRaises(IdempotencyConflictError):
            self.acceptance.accept(changed, at=self.now + timedelta(seconds=11))

    def test_same_quote_cannot_create_second_utt(self) -> None:
        quote = self._quote()
        self.acceptance.accept(
            self._command(idempotency_key="idem-001", quote=quote),
            at=self.now + timedelta(seconds=10),
        )
        with self.assertRaises(QuoteAlreadyAcceptedError):
            self.acceptance.accept(
                self._command(idempotency_key="idem-002", quote=quote),
                at=self.now + timedelta(seconds=11),
            )

    def test_expired_quote_is_rejected(self) -> None:
        with self.assertRaisesRegex(PermissionError, "QUOTE_EXPIRED"):
            self.acceptance.accept(
                self._command(), at=self.now + timedelta(seconds=60)
            )

    def test_tampered_quote_is_rejected(self) -> None:
        quote = self._quote()
        tampered = SignatureEnvelope(
            protected=quote.protected,
            payload={**quote.payload, "total_fee_minor": 1},
            signature=quote.signature,
        )
        with self.assertRaisesRegex(PermissionError, "PAYLOAD_HASH_MISMATCH"):
            self.acceptance.accept(
                self._command(quote=tampered), at=self.now + timedelta(seconds=10)
            )

    def test_p2p_is_a_first_class_accepted_origin(self) -> None:
        p2p_terms = QuoteTerms(
            request_id="REQ-P2P-001",
            payer=ActorReference(
                "PERSON", "CUID-SENDER", endpoint("BIND-PAYER-P2P", AccountRole.DEBIT)
            ),
            beneficiary=ActorReference(
                "PERSON", "CUID-RECEIVER", endpoint("BIND-BEN-P2P", AccountRole.CREDIT)
            ),
            purpose=PaymentPurpose.PERSON_TO_PERSON,
            amount_minor=100000,
            currency_from="KES",
            receive_amount_minor=99500,
            currency_to="KES",
            total_fee_minor=500,
            routing_budget_minor=200,
            fx_rate="1.000000",
            corridor_id="KE-DOMESTIC",
            service_level="STANDARD",
            routing_policy_id="POLICY-KE-P2P",
            pricing_version="2026-07",
        )
        quote = self.quotes.issue_quote(
            terms=p2p_terms,
            signing_key_id="R1CORE:quote:2026-01",
            issued_at=self.now,
            expires_at=self.now + timedelta(seconds=60),
        )
        command = QuoteAcceptanceCommand(
            signed_quote=quote,
            origin=OriginContext(
                origin_system="RAILONE_CLIENT",
                origin_intent_id="P2P-INTENT-001",
                context_type=ContextType.P2P,
                purpose=PaymentPurpose.PERSON_TO_PERSON,
                continuity_uid="CUID-SENDER",
            ),
            authorization_method="IDENTITY_SESSION_ATTESTATION",
            authorization_reference="P2P-AUTH-001",
            idempotency_key="idem-p2p-001",
        )

        result = self.acceptance.accept(
            command, at=self.now + timedelta(seconds=10)
        )

        self.assertEqual(
            result.contract.signed_utt.payload["origin"]["context_type"],
            "P2P",
        )
        self.assertEqual(
            result.contract.signed_utt.payload["origin"]["continuity_uid"],
            "CUID-SENDER",
        )

    def test_merchant_context_cannot_accept_another_merchant_quote(self) -> None:
        wrong_origin = OriginContext(
            origin_system="AVIA",
            origin_intent_id="AVIA-WRONG-MERCHANT",
            context_type=ContextType.MERCHANT,
            purpose=PaymentPurpose.SUPPLIER_PAYMENT,
            merchant_id="MER999",
        )
        command = QuoteAcceptanceCommand(
            signed_quote=self._quote(),
            origin=wrong_origin,
            authorization_method="MERCHANT_ACTOR_ATTESTATION",
            authorization_reference="AUTH-002",
            idempotency_key="idem-wrong-merchant",
        )

        with self.assertRaisesRegex(PermissionError, "merchant context"):
            self.acceptance.accept(
                command, at=self.now + timedelta(seconds=10)
            )

    def test_utt_guard_rejects_unknown_utt(self) -> None:
        with self.assertRaises(UttNotFoundError):
            self.store.require_utt("UTT-DOES-NOT-EXIST")


if __name__ == "__main__":
    unittest.main()
