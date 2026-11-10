"""Phase 3 signed canonical adapter wrapper: format, proof and fail-closed checks."""
from __future__ import annotations

import copy
import json
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from railone_crypto import InMemoryEd25519KeyProvider, KeyPurpose, SignatureService
from railone_crypto.signature_service import ArtifactType, SignatureEnvelope
from railone_institutions.wrapper_store import InMemoryDispatchWrapperStore
from railone_institutions.wrapper import (
    AuthoritativeDispatchSnapshot, CanonicalDispatchWrapper,
    DispatchWrapperService, SignedDispatchWrapper,
)

NOW = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
HEX = {"utt": "a" * 64, "rtt": "b" * 64, "sender": "c" * 64,
       "receiver": "d" * 64, "manifest": "e" * 64,
       "decision": "f" * 64, "request": "0" * 64}


def sections(*, replay=False):
    return {
        "trace_identifiers": {"utt_id": "UTT-SYN-01", "plan_id": "PLAN-SYN-01",
                              "rtt_id": "RTT-SYN-02" if replay else "RTT-SYN-01",
                              "correlation_id": "CORR-SYN-01", "attempt_number": 2 if replay else 1,
                              "replay_generation": 1 if replay else 0},
        "bilateral_trust_anchors": {"utt_payload_digest": HEX["utt"], "rtt_birth_digest": HEX["rtt"],
                                    "etk_s_digest": HEX["sender"], "etk_r_digest": HEX["receiver"],
                                    "sender_cont_uid": "CUID-SYN-SENDER", "recipient_cont_uid": "CUID-SYN-RECIPIENT"},
        "commercial_terms": {"source_amount_minor": 100000, "source_currency": "UGX",
                             "receive_amount_minor": 7150000, "receive_currency": "TZS",
                             "pricing_model": "PER_INTENT", "custody_model": "NON_CUSTODIAL"},
        "execution_binding": {"route_id": "ROUTE-SYN-01", "adapter_binding_ref": "synthetic.mtn-crdb@1.0.0",
                              "adapter_manifest_digest": HEX["manifest"], "route_decision_digest": HEX["decision"],
                              "idempotency_key": "IDEMP-SYN-01", "request_sha256": HEX["request"],
                              "provider_id": "SYN-UG-TZ-PROVIDER"},
        "fencing_controls": {"operational_mode": "SEQUENTIAL_RECONCILIATION_SAFE",
                             "economic_effect_fence_epoch": 1,
                             "dispatch_guard_decision": "RELEASED_FOR_THIS_ATTEMPT",
                             "release_evidence_ref": "RECON-SYN-NO-EFFECT" if replay else None},
        "protected_account_bindings": {"payer_binding_ref": "acctbind_ug_synthetic_0001",
                                       "beneficiary_binding_ref": "acctbind_tz_synthetic_0002",
                                       "source_routing_node": "UG-MTN-MOBILE-MONEY",
                                       "destination_routing_node": "TZ-CRDB-BANK-PLC"},
    }


def snapshot(payload):
    return AuthoritativeDispatchSnapshot(
        utt_id=payload["trace_identifiers"]["utt_id"],
        plan_id=payload["trace_identifiers"]["plan_id"],
        rtt_id=payload["trace_identifiers"]["rtt_id"],
        attempt_number=payload["trace_identifiers"]["attempt_number"],
        replay_generation=payload["trace_identifiers"]["replay_generation"],
        correlation_id=payload["trace_identifiers"]["correlation_id"],
        utt_payload_digest=payload["bilateral_trust_anchors"]["utt_payload_digest"],
        rtt_birth_digest=payload["bilateral_trust_anchors"]["rtt_birth_digest"],
        etk_s_digest=payload["bilateral_trust_anchors"]["etk_s_digest"],
        etk_r_digest=payload["bilateral_trust_anchors"]["etk_r_digest"],
        sender_cont_uid=payload["bilateral_trust_anchors"]["sender_cont_uid"],
        recipient_cont_uid=payload["bilateral_trust_anchors"]["recipient_cont_uid"],
        adapter_binding_ref=payload["execution_binding"]["adapter_binding_ref"],
        adapter_manifest_digest=payload["execution_binding"]["adapter_manifest_digest"],
        route_decision_digest=payload["execution_binding"]["route_decision_digest"],
        route_id=payload["execution_binding"]["route_id"],
        provider_id=payload["execution_binding"]["provider_id"],
        request_sha256=payload["execution_binding"]["request_sha256"],
        idempotency_key=payload["execution_binding"]["idempotency_key"],
        source_amount_minor=payload["commercial_terms"]["source_amount_minor"],
        source_currency=payload["commercial_terms"]["source_currency"],
        receive_amount_minor=payload["commercial_terms"]["receive_amount_minor"],
        receive_currency=payload["commercial_terms"]["receive_currency"],
        payer_binding_ref=payload["protected_account_bindings"]["payer_binding_ref"],
        beneficiary_binding_ref=payload["protected_account_bindings"]["beneficiary_binding_ref"],
        source_routing_node=payload["protected_account_bindings"]["source_routing_node"],
        destination_routing_node=payload["protected_account_bindings"]["destination_routing_node"],
        economic_effect_fence_epoch=payload["fencing_controls"]["economic_effect_fence_epoch"],
        release_evidence_ref=payload["fencing_controls"]["release_evidence_ref"],
    )


class InstitutionDispatchWrapperTests(unittest.TestCase):
    def setUp(self):
        self.keys = InMemoryEd25519KeyProvider()
        self.keys.generate(key_id="railone-wrapper-test", owner_id="RAILONE",
                           purpose=KeyPurpose.EXECUTION_SIGNING,
                           not_before=NOW - timedelta(days=1),
                           not_after=NOW + timedelta(days=1))
        self.signatures = SignatureService(self.keys)
        self.service = DispatchWrapperService(self.signatures, signing_key_id="railone-wrapper-test")
        self.wrapper = CanonicalDispatchWrapper.build(
            issued_at_epoch=int(NOW.timestamp()), expires_at_epoch=int(NOW.timestamp())+30,
            **sections())
        self.expected = snapshot(self.wrapper.to_payload())

    def test_wrapper_signs_and_verifies_at_bound_instant(self):
        signed = self.service.issue(self.wrapper, expected=self.expected, at=NOW)
        verified = self.service.verify(signed, expected=self.expected, at=NOW + timedelta(seconds=5))
        self.assertEqual(verified, self.wrapper)
        self.assertEqual(signed.signature.protected["typ"], ArtifactType.INSTITUTION_DISPATCH_WRAPPER.value)

    def test_canonical_order_has_no_effect_on_hash(self):
        original = self.wrapper.to_payload()
        rehydrated = CanonicalDispatchWrapper.from_payload(dict(reversed(list(original.items()))))
        self.assertEqual(rehydrated.wrapper_sha256, self.wrapper.wrapper_sha256)
        self.assertEqual(rehydrated.canonical_body, self.wrapper.canonical_body)

    def test_root_and_subsection_unknown_fields_rejected(self):
        body = self.wrapper.to_payload()
        body["raw_sender_msisdn"] = "+256772000000"
        with self.assertRaises(ValueError):
            CanonicalDispatchWrapper.from_payload(body)
        body = self.wrapper.to_payload()
        body["protected_account_bindings"]["raw_receiver_account"] = "000123"
        with self.assertRaises(ValueError):
            CanonicalDispatchWrapper.from_payload(body)

    def test_opaque_account_refs_required(self):
        body = self.wrapper.to_payload()
        body["protected_account_bindings"]["payer_binding_ref"] = "+256772000000"
        with self.assertRaises(ValueError):
            CanonicalDispatchWrapper.from_payload(body)

    def test_replay_requires_authoritative_release_reference(self):
        body = sections(replay=True)
        body["fencing_controls"]["release_evidence_ref"] = None
        with self.assertRaises(ValueError):
            CanonicalDispatchWrapper.build(issued_at_epoch=int(NOW.timestamp()),
                                           expires_at_epoch=int(NOW.timestamp())+30, **body)
        body["fencing_controls"]["release_evidence_ref"] = "RECON-SYN-NO-EFFECT"
        valid = CanonicalDispatchWrapper.build(issued_at_epoch=int(NOW.timestamp()),
                                               expires_at_epoch=int(NOW.timestamp())+30, **body)
        self.assertEqual(valid.to_payload()["trace_identifiers"]["attempt_number"], 2)

    def test_parallel_splits_not_allowed_at_this_stage(self):
        body = sections()
        body["fencing_controls"]["operational_mode"] = "SPLIT_NON_BLOCKING"
        with self.assertRaises(ValueError):
            CanonicalDispatchWrapper.build(issued_at_epoch=int(NOW.timestamp()),
                                           expires_at_epoch=int(NOW.timestamp())+30, **body)

    def test_rejects_float_bool_negative_currency_and_cross_currency_amount_change(self):
        for section, key, invalid in (("commercial_terms", "source_amount_minor", 1.5),
                                      ("commercial_terms", "source_amount_minor", True),
                                      ("commercial_terms", "source_amount_minor", -1),
                                      ("commercial_terms", "receive_currency", "TZSH")):
            body = sections()
            body[section][key] = invalid
            with self.subTest(field=key, value=invalid), self.assertRaises(ValueError):
                CanonicalDispatchWrapper.build(issued_at_epoch=int(NOW.timestamp()),
                                               expires_at_epoch=int(NOW.timestamp())+30, **body)

    def test_forged_payload_fails_signature_check(self):
        signed = self.service.issue(self.wrapper, expected=self.expected, at=NOW)
        changed = signed.signature.to_dict()
        changed["payload"]["commercial_terms"]["source_amount_minor"] = 1
        tampered = SignedDispatchWrapper(signed.wrapper, SignatureEnvelope.from_dict(changed))
        with self.assertRaises(PermissionError):
            self.service.verify(tampered, expected=self.expected, at=NOW)

    def test_mismatched_expected_route_decision_or_fence_fails_closed(self):
        signed = self.service.issue(self.wrapper, expected=self.expected, at=NOW)
        for key, value in (("route_decision_digest", "1" * 64), ("adapter_binding_ref", "malign@2.0.0"),
                           ("economic_effect_fence_epoch", 2), ("source_amount_minor", 123),
                           ("etk_r_digest", "9"*64), ("provider_id", "EVIL"),
                           ("beneficiary_binding_ref", "acctbind_bad_000")):
            with self.subTest(key=key), self.assertRaises(PermissionError):
                self.service.verify(signed, expected=replace(self.expected, **{key:value}), at=NOW)

    def test_expired_or_early_envelope_rejected(self):
        signed = self.service.issue(self.wrapper, expected=self.expected, at=NOW)
        for delta in (-1, 30, 600):
            with self.subTest(delta=delta), self.assertRaises(PermissionError):
                self.service.verify(signed, expected=self.expected, at=NOW + timedelta(seconds=delta))

    def test_wrong_signature_artifact_type_rejected(self):
        wrong = self.signatures.sign_artifact(artifact_type=ArtifactType.RTT,
                payload=self.wrapper.to_payload(), key_id="railone-wrapper-test", issued_at=NOW)
        with self.assertRaises(PermissionError):
            self.service.verify(SignedDispatchWrapper(self.wrapper, wrong), expected=self.expected, at=NOW)

    def test_untrusted_signer_owner_rejected(self):
        other_keys = InMemoryEd25519KeyProvider()
        other_keys.generate(key_id="outside", owner_id="ADAPTER",
                            purpose=KeyPurpose.EXECUTION_SIGNING,
                            not_before=NOW-timedelta(hours=1), not_after=NOW+timedelta(hours=1))
        other_service = DispatchWrapperService(SignatureService(other_keys), signing_key_id="outside")
        with self.assertRaises(PermissionError):
            other_service.issue(self.wrapper, expected=self.expected, at=NOW)

    def test_store_duplicate_is_idempotent_and_conflict_is_rejected(self):
        store = InMemoryDispatchWrapperStore(self.service)
        signed = self.service.issue(self.wrapper, expected=self.expected, at=NOW)
        self.assertEqual(store.put(signed, expected=self.expected, at=NOW), signed)
        self.assertEqual(store.put(signed, expected=self.expected, at=NOW), signed)
        self.assertEqual(store.require("RTT-SYN-01"), signed)
        different = CanonicalDispatchWrapper.build(
            issued_at_epoch=int(NOW.timestamp()), expires_at_epoch=int(NOW.timestamp())+20,
            **sections())
        different_signed = self.service.issue(different, expected=self.expected, at=NOW)
        with self.assertRaises(ValueError):
            store.put(different_signed, expected=self.expected, at=NOW)

    def test_store_rejects_forged_wrapper_before_persistence(self):
        store = InMemoryDispatchWrapperStore(self.service)
        signed = self.service.issue(self.wrapper, expected=self.expected, at=NOW)
        changed = signed.signature.to_dict()
        changed["payload"]["execution_binding"]["route_id"] = "UNAUTHORIZED"
        with self.assertRaises(PermissionError):
            store.put(SignedDispatchWrapper(self.wrapper, SignatureEnvelope.from_dict(changed)),
                      expected=self.expected, at=NOW)
        with self.assertRaises(LookupError):
            store.require("RTT-SYN-01")

    def test_reject_expiry_window_larger_than_one_minute(self):
        with self.assertRaises(ValueError):
            CanonicalDispatchWrapper.build(issued_at_epoch=int(NOW.timestamp()),
                                           expires_at_epoch=int(NOW.timestamp())+61, **sections())

    def test_additive_migration_enforces_append_only_and_fk_bindings(self):
        migration = (Path(__file__).resolve().parents[1] / "migrations" /
                     "0013_signed_institution_dispatch_wrappers.sql").read_text()
        self.assertIn("REFERENCES railone.route_decision_records(decision_sha256)", migration)
        self.assertIn("REFERENCES railone.institution_adapter_manifests(binding_ref)", migration)
        self.assertIn("REFERENCES railone.rtt_attempts(rtt_id)", migration)
        self.assertIn("BEFORE UPDATE OR DELETE", migration)
        self.assertIn("UNIQUE REFERENCES railone.rtt_attempts", migration)

    def test_immutable_wrapped_values_not_exposed(self):
        body = self.wrapper.to_payload()
        body["commercial_terms"]["source_amount_minor"] = 1
        self.assertEqual(self.wrapper.to_payload()["commercial_terms"]["source_amount_minor"], 100000)


if __name__ == "__main__":
    unittest.main()
