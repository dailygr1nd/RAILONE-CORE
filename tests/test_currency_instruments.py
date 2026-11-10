"""New additive v0.16.0 currency/settlement metadata contract tests."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

from railone_currency import (
    CurrencyDefinition, CurrencyInstrumentRegistry, InstrumentEnvironment,
    MonetaryIssuerKind, ProfileReviewStatus, SettlementInstrumentKind,
    SettlementInstrumentProfile,
)

ROOT = Path(__file__).resolve().parents[1]


def tzs(version: int = 1) -> CurrencyDefinition:
    return CurrencyDefinition(
        currency_code="TZS", definition_version=version, minor_unit_exponent=2,
        issuing_authority_ref="BOT", standard_reference="ISO4217-TZS",
    )


def profile(**changes) -> SettlementInstrumentProfile:
    base = dict(
        profile_id="TIPS-TZS-COMMERCIAL-BANK", profile_version=1,
        currency_code="TZS", currency_definition_version=1,
        instrument_kind=SettlementInstrumentKind.COMMERCIAL_BANK_MONEY,
        issuer_kind=MonetaryIssuerKind.LICENSED_BANK,
        issuer_institution_id="BANK-TEST", operator_institution_id="TIPS-TEST",
        settlement_rail_id="TIPS-SYNTHETIC", jurisdiction_country="TZ",
        environment=InstrumentEnvironment.SANDBOX,
    )
    return SettlementInstrumentProfile(**(base | changes))


class CurrencyInstrumentContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = CurrencyInstrumentRegistry()
        self.registry.add_currency(tzs())

    def test_currency_snapshot_is_immutable(self):
        with self.assertRaises(FrozenInstanceError):
            tzs().currency_code = "KES"

    def test_currency_requires_uppercase_three_letter_code(self):
        for bad in ("tzs", "TzS", "TZ", "TZSS", "123", "BTC-USD"):
            with self.subTest(code=bad), self.assertRaises(ValueError):
                replace(tzs(), currency_code=bad)

    def test_minor_units_reject_negative_bool_noninteger(self):
        for invalid in (-1, 10, True, False, 2.5, "2"):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                replace(tzs(), minor_unit_exponent=invalid)

    def test_currency_revision_is_idempotent_and_immutable(self):
        self.assertEqual(self.registry.add_currency(tzs()), tzs())
        with self.assertRaises(ValueError):
            self.registry.add_currency(replace(tzs(), minor_unit_exponent=0))
        self.registry.add_currency(tzs(2))
        self.assertEqual(self.registry.currency("TZS").definition_version, 2)
        self.assertEqual(self.registry.currency("TZS", version=1), tzs())

    def test_currency_revision_cannot_skip_versions(self):
        with self.assertRaises(ValueError):
            self.registry.add_currency(tzs(3))

    def test_profile_requires_existing_currency_revision(self):
        with self.assertRaises(KeyError):
            self.registry.add_profile(profile(currency_definition_version=3))

    def test_declared_profile_is_not_implicitly_reviewed(self):
        item = self.registry.add_profile(profile())
        self.assertEqual(item.review_status, ProfileReviewStatus.DECLARED)
        self.assertIsNone(item.review_evidence_ref)

    def test_reviewed_profile_requires_evidence(self):
        with self.assertRaises(ValueError):
            profile(review_status=ProfileReviewStatus.REVIEWED)
        self.assertEqual(
            profile(review_status=ProfileReviewStatus.REVIEWED, review_evidence_ref="AUDIT-TEST-001")
            .review_status, ProfileReviewStatus.REVIEWED,
        )

    def test_cbdc_must_have_central_bank_issuer(self):
        for kind in (SettlementInstrumentKind.RETAIL_CBDC, SettlementInstrumentKind.WHOLESALE_CBDC):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                profile(instrument_kind=kind)
            value = profile(
                instrument_kind=kind, issuer_kind=MonetaryIssuerKind.CENTRAL_BANK,
                issuer_institution_id="CENTRAL-BANK-TEST",
                profile_id=f"SYNTHETIC-{kind.value}",
            )
            self.assertEqual(value.instrument_kind, kind)

    def test_emoney_requires_regulated_emoney_issuer(self):
        with self.assertRaises(ValueError):
            profile(instrument_kind=SettlementInstrumentKind.REGULATED_E_MONEY)
        valid = profile(
            instrument_kind=SettlementInstrumentKind.REGULATED_E_MONEY,
            issuer_kind=MonetaryIssuerKind.REGULATED_EMONEY_ISSUER,
        )
        self.assertEqual(valid.issuer_kind, MonetaryIssuerKind.REGULATED_EMONEY_ISSUER)

    def test_crypto_asset_is_not_an_instrument_type(self):
        with self.assertRaises(ValueError):
            SettlementInstrumentKind("CRYPTO_ASSET")
        with self.assertRaises(ValueError):
            SettlementInstrumentKind("STABLECOIN")

    def test_profile_revision_cannot_be_rewritten(self):
        self.registry.add_profile(profile())
        self.assertEqual(self.registry.add_profile(profile()), profile())
        with self.assertRaises(ValueError):
            self.registry.add_profile(profile(operator_institution_id="OTHER-OPERATOR"))

    def test_profile_revision_must_be_sequential(self):
        with self.assertRaises(ValueError):
            self.registry.add_profile(profile(profile_version=2))
        self.registry.add_profile(profile())
        with self.assertRaises(ValueError):
            self.registry.add_profile(profile(profile_version=3))
        self.registry.add_profile(profile(profile_version=2,
                                          review_status=ProfileReviewStatus.REVIEWED,
                                          review_evidence_ref="AUDIT-TEST-001"))
        self.assertEqual(self.registry.profile("TIPS-TZS-COMMERCIAL-BANK").profile_version, 2)

    def test_profile_identity_cannot_shift_currency_or_issuer_or_rail(self):
        self.registry.add_profile(profile())
        for updates in (
            {"currency_code": "KES"}, {"issuer_institution_id": "BANK-OTHER"},
            {"settlement_rail_id": "OTHER-RAIL"},
        ):
            with self.subTest(change=updates):
                # KES needs a valid currency reference, too.
                if updates.get("currency_code") == "KES":
                    self.registry.add_currency(CurrencyDefinition(
                        "KES", 1, 2, "CBK", "ISO4217-KES"))
                with self.assertRaises(ValueError):
                    self.registry.add_profile(profile(profile_version=2, **updates))

    def test_retrieval_is_sorted_and_latest_version(self):
        self.registry.add_profile(profile())
        self.registry.add_profile(profile(profile_version=2,
                                          review_status=ProfileReviewStatus.SUSPENDED))
        self.registry.add_profile(profile(profile_id="A-SANDBOX-EMONEY",
                                          instrument_kind=SettlementInstrumentKind.REGULATED_E_MONEY,
                                          issuer_kind=MonetaryIssuerKind.REGULATED_EMONEY_ISSUER))
        self.assertEqual(
            tuple(x.profile_id for x in self.registry.declared_profiles(currency_code="TZS")),
            ("A-SANDBOX-EMONEY", "TIPS-TZS-COMMERCIAL-BANK"),
        )
        self.assertEqual(
            self.registry.profile("TIPS-TZS-COMMERCIAL-BANK").review_status,
            ProfileReviewStatus.SUSPENDED,
        )

    def test_payload_contains_no_account_or_private_key_material(self):
        payload = profile().to_payload()
        self.assertNotIn("raw_sender_msisdn", payload)
        self.assertNotIn("raw_receiver_account", payload)
        self.assertNotIn("private_key", payload)
        self.assertEqual(payload["environment"], "SANDBOX")

    def test_migration_0011_is_additive_and_append_only(self):
        ddl = (ROOT / "migrations" / "0011_currency_and_settlement_instruments.sql").read_text()
        self.assertIn("CREATE TABLE railone.currency_definitions", ddl)
        self.assertIn("CREATE TABLE railone.settlement_instrument_profiles", ddl)
        self.assertIn("currency_definitions_append_only", ddl)
        self.assertIn("settlement_instrument_profiles_append_only", ddl)
        self.assertNotIn("DROP TABLE", ddl.upper())
        self.assertIn("FOREIGN KEY (currency_code, currency_definition_version)", ddl)

    def test_existing_utt_rtt_orchestration_packages_are_untouched_by_registry(self):
        # A new metadata record cannot make itself an allowed execution route.
        paths = [ROOT / "railone_contracts" / "models.py",
                 ROOT / "railone_execution" / "service.py",
                 ROOT / "railone_operations" / "service.py"]
        for path in paths:
            self.assertNotIn("from railone_currency", path.read_text())


if __name__ == "__main__":
    unittest.main()
