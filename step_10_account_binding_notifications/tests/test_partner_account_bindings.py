from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from railone_contracts import (
    AccountRole, AccountType, ActorReference, PaymentPurpose, QuoteService, QuoteTerms,
)
from railone_crypto.key_provider import InMemoryEd25519KeyProvider, KeyPurpose
from railone_crypto.signature_service import SignatureService
from railone_partners import (
    AccountBinding, InMemoryPartnerDirectory, InstitutionStatus,
    PartnerInstitution,
)


class PartnerAccountBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 7, 14, 17, 0, tzinfo=timezone.utc)
        self.directory = InMemoryPartnerDirectory()
        self.directory.add_institution(PartnerInstitution(
            institution_id="BANK-KE-001", display_name="Pilot Bank",
            country_codes=("KE",), currencies=("KES",),
            supported_roles=(AccountRole.DEBIT, AccountRole.CREDIT),
        ))
        self.directory.add_institution(PartnerInstitution(
            institution_id="PAUSED-KE", display_name="Paused Bank",
            country_codes=("KE",), currencies=("KES",),
            supported_roles=(AccountRole.DEBIT,), status=InstitutionStatus.PAUSED,
        ))
        self.directory.add_binding(AccountBinding(
            account_binding_id="BIND-SENDER", actor_id="CUID-SENDER",
            institution_id="BANK-KE-001", role=AccountRole.DEBIT,
            account_type=AccountType.BANK_ACCOUNT, currency="KES",
            display_hint="****1111", contact_binding_id="CONTACT-SENDER",
            attestation_reference="ATTEST-SENDER",
        ))
        self.directory.add_binding(AccountBinding(
            account_binding_id="BIND-RECEIVER", actor_id="CUID-RECEIVER",
            institution_id="BANK-KE-001", role=AccountRole.CREDIT,
            account_type=AccountType.BANK_ACCOUNT, currency="KES",
            display_hint="****2222", contact_binding_id="CONTACT-RECEIVER",
            attestation_reference="ATTEST-RECEIVER",
        ))

    def test_partner_list_only_returns_active_eligible_institutions(self) -> None:
        rows = self.directory.list_institutions(
            country_code="KE", currency="KES", role=AccountRole.DEBIT
        )
        self.assertEqual(tuple(item.institution_id for item in rows), ("BANK-KE-001",))

    def test_actor_cannot_select_another_users_account_binding(self) -> None:
        with self.assertRaises(PermissionError):
            self.directory.select_endpoint(
                actor_id="CUID-OTHER", account_binding_id="BIND-SENDER",
                required_role=AccountRole.DEBIT,
            )

    def test_quote_binds_validated_opaque_endpoints_and_no_raw_account(self) -> None:
        keys = InMemoryEd25519KeyProvider()
        keys.generate(
            key_id="quote", owner_id="R1CORE", purpose=KeyPurpose.QUOTE_SIGNING,
            not_before=self.now - timedelta(days=1),
            not_after=self.now + timedelta(days=30),
        )
        sender = self.directory.select_endpoint(
            actor_id="CUID-SENDER", account_binding_id="BIND-SENDER",
            required_role=AccountRole.DEBIT,
        )
        receiver = self.directory.select_endpoint(
            actor_id="CUID-RECEIVER", account_binding_id="BIND-RECEIVER",
            required_role=AccountRole.CREDIT,
        )
        quote = QuoteService(
            SignatureService(keys), endpoints=self.directory
        ).issue_quote(
            terms=QuoteTerms(
                request_id="REQ-BIND-001",
                payer=ActorReference("PERSON", "CUID-SENDER", sender, "Noel"),
                beneficiary=ActorReference(
                    "PERSON", "CUID-RECEIVER", receiver, "Amina"
                ),
                purpose=PaymentPurpose.PERSON_TO_PERSON,
                amount_minor=10_000, currency_from="KES",
                receive_amount_minor=10_000, currency_to="KES",
                total_fee_minor=0, routing_budget_minor=0, fx_rate="1.000000",
                corridor_id="KE-DOMESTIC", service_level="STANDARD",
                routing_policy_id="POLICY-KE", pricing_version="2026-07",
            ),
            signing_key_id="quote", issued_at=self.now,
            expires_at=self.now + timedelta(minutes=1),
        )
        rendered = repr(quote.to_dict())
        self.assertIn("BIND-SENDER", rendered)
        self.assertIn("BANK-KE-001", rendered)
        self.assertNotIn("account_reference", rendered)

    def test_quote_service_fails_closed_without_partner_validator(self) -> None:
        keys = InMemoryEd25519KeyProvider()
        keys.generate(
            key_id="quote", owner_id="R1CORE", purpose=KeyPurpose.QUOTE_SIGNING,
            not_before=self.now - timedelta(days=1),
            not_after=self.now + timedelta(days=30),
        )
        with self.assertRaisesRegex(RuntimeError, "endpoint validator"):
            QuoteService(SignatureService(keys)).issue_quote(
                terms=QuoteTerms(
                    request_id="REQ", payer=ActorReference(
                        "PERSON", "CUID-SENDER",
                        self.directory.select_endpoint(
                            actor_id="CUID-SENDER", account_binding_id="BIND-SENDER",
                            required_role=AccountRole.DEBIT,
                        ),
                    ),
                    beneficiary=ActorReference(
                        "PERSON", "CUID-RECEIVER",
                        self.directory.select_endpoint(
                            actor_id="CUID-RECEIVER", account_binding_id="BIND-RECEIVER",
                            required_role=AccountRole.CREDIT,
                        ),
                    ),
                    purpose=PaymentPurpose.PERSON_TO_PERSON,
                    amount_minor=100, currency_from="KES", receive_amount_minor=100,
                    currency_to="KES", total_fee_minor=0, routing_budget_minor=0,
                    fx_rate="1", corridor_id="KE", service_level="STANDARD",
                    routing_policy_id="POLICY", pricing_version="v1",
                ),
                signing_key_id="quote", issued_at=self.now,
                expires_at=self.now + timedelta(minutes=1),
            )


if __name__ == "__main__":
    unittest.main()
