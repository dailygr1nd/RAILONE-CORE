"""Sender-first ETK -> UTT -> RTT and compromised institution conformance.

Synthetic keys, no external funds. Tests fail if authorization can be bypassed.
"""

from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from railone_authority import ExecutionAuthorityService
from railone_authority.bilateral import BilateralAuthorityService
from railone_contracts import (
    AccountRole, ActorReference, ContextType, InMemoryContractStore,
    OriginContext, PaymentPurpose, QuoteAcceptanceCommand,
    QuoteAcceptanceService, QuoteTerms,
)
from railone_crypto.key_provider import InMemoryEd25519KeyProvider, KeyPurpose
from railone_crypto.signature_service import SignatureEnvelope, SignatureService, ArtifactType
from railone_execution import (
    ExecutionPlanningService, InMemoryExecutionStore, LinkStatus,
    NoEligibleRouteError, RouteCandidate, RttAttemptService,
)
from railone_institutions.admission import InstitutionalDispatchAdmissionGateway
from railone_security.incident_audit import rejection_code
from tests.support import endpoint, quote_service
from railone_partners import AccountBinding, PartnerInstitution, InMemoryPartnerDirectory


class Recorder:
    def __init__(self):
        self.events = []

    def record_rejection(self, **kwargs):
        self.events.append({
            "event_type": kwargs["event_type"],
            "operation": kwargs["operation"],
            "correlation_ref": kwargs["correlation_ref"],
            "reason_code": rejection_code(kwargs["error"]),
            "outcome": "DENIED",
        })


class CompromisedInstitutionHarnessTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)
        self.keys = InMemoryEd25519KeyProvider()
        for owner, name, purpose in (
            ("R1CORE", "quote", KeyPurpose.QUOTE_SIGNING),
            ("R1CORE", "core", KeyPurpose.EXECUTION_SIGNING),
            ("CUID-SENDER", "sender", KeyPurpose.EXECUTION_SIGNING),
            ("CUID-RECEIVER", "receiver", KeyPurpose.EXECUTION_SIGNING),
            ("CUID-ROGUE", "rogue", KeyPurpose.EXECUTION_SIGNING),
        ):
            self.keys.generate(
                key_id=name, owner_id=owner, purpose=purpose,
                not_before=self.now-timedelta(days=1),
                not_after=self.now+timedelta(days=2),
            )
        self.signatures = SignatureService(self.keys)
        self.bilateral = BilateralAuthorityService(self.signatures)
        self.contracts = InMemoryContractStore()
        self.executions = InMemoryExecutionStore(self.contracts)
        self.audit = Recorder()
        self.accept = QuoteAcceptanceService(
            signatures=self.signatures,
            authority=ExecutionAuthorityService(self.signatures),
            store=self.contracts,
            utt_signing_key_id="core", authority_signing_key_id="core",
            require_bilateral_p2p=True, security_audit=self.audit,
        )
        self.directory = InMemoryPartnerDirectory()
        for institution, role in (("INST-SOURCE", AccountRole.DEBIT),
                                  ("INST-DEST", AccountRole.CREDIT)):
            self.directory.add_institution(PartnerInstitution(
                institution_id=institution, display_name=institution,
                country_codes=("KE",), currencies=("KES",),
                supported_roles=(role,),
            ))
        from railone_contracts import AccountType
        for binding, actor, institution, role in (
            ("BIND-TZ", "CUID-SENDER", "INST-SOURCE", AccountRole.DEBIT),
            ("BIND-KE", "CUID-RECEIVER", "INST-DEST", AccountRole.CREDIT),
        ):
            self.directory.add_binding(AccountBinding(
                account_binding_id=binding, actor_id=actor,
                institution_id=institution, role=role,
                account_type=AccountType.BANK_ACCOUNT, currency="KES",
                display_hint="****1111" if role is AccountRole.DEBIT else "****2222",
                contact_binding_id=f"CONTACT-{binding}",
                attestation_reference=f"ATTEST-{binding}",
            ))
        self.plan = ExecutionPlanningService(
            signatures=self.signatures, contracts=self.contracts,
            executions=self.executions, security_audit=self.audit,
        )
        self.attempt = RttAttemptService(
            signatures=self.signatures, contracts=self.contracts,
            executions=self.executions, rtt_signing_key_id="core",
            endpoints=self.directory, security_audit=self.audit,
        )
        self.origin = OriginContext(
            origin_system="RAILONE_CLIENT", origin_intent_id="TEST-P2P-001",
            context_type=ContextType.P2P, purpose=PaymentPurpose.PERSON_TO_PERSON,
            continuity_uid="CUID-SENDER",
        )
        self.terms = QuoteTerms(
            request_id="REQ-SYNTH-001",
            payer=ActorReference("PERSON", "CUID-SENDER", endpoint("BIND-TZ", AccountRole.DEBIT)),
            beneficiary=ActorReference("PERSON", "CUID-RECEIVER", endpoint("BIND-KE", AccountRole.CREDIT)),
            purpose=PaymentPurpose.PERSON_TO_PERSON,
            amount_minor=125000, currency_from="KES", receive_amount_minor=124500,
            currency_to="KES", total_fee_minor=500, routing_budget_minor=200,
            fx_rate="1.0000", corridor_id="SYNTH-TZ-KE", service_level="STANDARD",
            routing_policy_id="POLICY-SANDBOX", pricing_version="2026-SYNTH",
        )
        self.quote = self.make_quote()

    def make_quote(self, terms=None):
        return quote_service(self.signatures).issue_quote(
            terms=terms or self.terms, signing_key_id="quote",
            issued_at=self.now, expires_at=self.now + timedelta(seconds=60),
        )

    def sender(self, quote=None, *, signing_key_id="sender", expires=180):
        return self.bilateral.issue_sender_authority(
            signed_quote=quote or self.quote, signing_key_id=signing_key_id,
            authorized_at=self.now + timedelta(seconds=5),
            expires_at=self.now + timedelta(seconds=expires),
        )

    def receiver(self, sender=None, quote=None, *, signing_key_id="receiver", expires=120):
        return self.bilateral.issue_receiver_acceptance(
            signed_quote=quote or self.quote, sender=sender or self.sender(quote=quote),
            signing_key_id=signing_key_id,
            accepted_at=self.now + timedelta(seconds=7),
            expires_at=self.now + timedelta(seconds=expires),
        )

    def command(self, receiver=None, quote=None, sender=None):
        # Tests explicitly simulate external sender signing. A caller cannot
        # ask RailOne acceptance to produce a payer signature on its behalf.
        if sender is None and receiver is not None:
            # A fixture's default sender signs the original quote; explicit
            # sender inputs simulate other valid or malicious chains.
            sender = self.sender()
        return QuoteAcceptanceCommand(
            signed_quote=quote or self.quote, origin=self.origin,
            authorization_method="IDENTITY_SESSION_ATTESTATION",
            authorization_reference="SESSION-SYNTH-001", idempotency_key="IDEM-P2P-SYNTH",
            receiver_authority=receiver, sender_authority=sender,
        )

    def accept_valid(self):
        return self.accept.accept(self.command(self.receiver()), at=self.now+timedelta(seconds=10))

    def route(self, *, destination="INST-DEST"):
        return RouteCandidate(
            route_id="SYNTH-FAST", source_institution_id="INST-SOURCE",
            destination_institution_id=destination, rail="SYNTHETIC",
            provider="SYNTH-BANK", adapter="sandbox-synth-1",
            currency_from="KES", currency_to="KES", min_amount_minor=1,
            max_amount_minor=500000, latency_ms=200, congestion_bps=50,
            liquidity_capacity_minor=1000000, throughput_headroom_bps=8500,
            speed_bps=9600, estimated_cost_minor=100, link_status=LinkStatus.UP,
            telemetry_observed_at=self.now,
            telemetry_expires_at=self.now + timedelta(minutes=5),
        )

    def test_00_strict_idempotency_cannot_return_legacy_p2p_utt(self):
        legacy = QuoteAcceptanceService(
            signatures=self.signatures,
            authority=ExecutionAuthorityService(self.signatures),
            store=self.contracts,
            utt_signing_key_id="core", authority_signing_key_id="core",
            require_bilateral_p2p=False,
        )
        command = self.command(None)
        prior = legacy.accept(command, at=self.now + timedelta(seconds=10))
        self.assertNotEqual(prior.contract.signed_utt.payload.get("authority_version"), 3)
        with self.assertRaisesRegex(PermissionError, "SENDER_FIRST_BILATERAL_V3_REQUIRED"):
            self.accept.accept(command, at=self.now + timedelta(seconds=11))
        self.assertEqual(len(self.contracts._utts), 1)

    def test_01_sender_first_bilateral_to_signed_utt_and_rtt(self):
        s = self.sender()
        r = self.receiver(s)
        accepted = self.accept.accept(self.command(r, sender=s), at=self.now+timedelta(seconds=10))
        c = accepted.contract
        self.assertEqual(c.signed_utt.payload["authority_version"], 3)
        self.assertEqual(c.receiver_authority.payload["etk_s_id"], s.payload["etk_s_id"])
        self.assertLess(s.protected["iat"], c.receiver_authority.protected["iat"])
        self.assertLessEqual(c.receiver_authority.protected["iat"], c.signed_utt.protected["iat"])
        self.assertEqual(c.signed_utt.payload["etk_r_digest"], r.protected["payload_sha256"])
        self.bilateral.verify_utt(signed_utt=c.signed_utt, sender=c.sender_authority,
                                  receiver=c.receiver_authority, at=self.now+timedelta(seconds=11))
        plan = self.plan.build_plan(utt_id=c.utt_id, candidates=(self.route(),),
                                    at=self.now+timedelta(seconds=11))
        rtt = self.attempt.start_next(utt_id=c.utt_id, at=self.now+timedelta(seconds=12))
        self.assertEqual(rtt.plan_id, plan.plan_id)
        self.assertEqual(rtt.signed_rtt.payload["utt_payload_sha256"], c.signed_utt.protected["payload_sha256"])
        self.assertEqual(len(self.audit.events), 0)

    def test_02_missing_receiver_approval_blocks_utt(self):
        # A sender ETK-S alone must never create a UTT.
        with self.assertRaisesRegex(PermissionError, "BILATERAL_P2P_AUTHORITIES_REQUIRED"):
            self.accept.accept(self.command(None, sender=self.sender()), at=self.now+timedelta(seconds=10))
        self.assertFalse(self.contracts._utts)

    def test_03_receiver_acceptance_cannot_be_signed_by_rogue_institution(self):
        with self.assertRaisesRegex(PermissionError, "BILATERAL_SIGNER_OWNER_MISMATCH"):
            self.receiver(signing_key_id="rogue")
        self.assertFalse(self.contracts._utts)

    def test_04_receiver_signature_tampering_fails_and_is_audited(self):
        r = self.receiver()
        bad = SignatureEnvelope(r.protected, {**r.payload, "amount_minor": 1}, r.signature)
        with self.assertRaisesRegex(PermissionError, "BILATERAL_SIGNATURE_INVALID"):
            self.accept.accept(self.command(bad), at=self.now+timedelta(seconds=10))
        self.assertEqual(self.audit.events[0]["reason_code"], "BILATERAL_SIGNATURE_INVALID")
        self.assertFalse(self.contracts._utts)

    def test_05_receiver_authority_cannot_be_replayed_on_another_quote(self):
        new_quote = self.make_quote(replace(self.terms, amount_minor=140000, request_id="REQ-ALTERED"))
        with self.assertRaisesRegex(PermissionError, "RECEIVER_QUOTE_BINDING_MISMATCH"):
            self.accept.accept(self.command(self.receiver(), quote=new_quote,
                                            sender=self.sender(quote=new_quote)),
                               at=self.now+timedelta(seconds=10))
        self.assertEqual(self.audit.events[0]["reason_code"], "RECEIVER_QUOTE_BINDING_MISMATCH")
        self.assertFalse(self.contracts._utts)

    def test_06_expired_receiver_consent_prevents_utt(self):
        r = self.receiver(expires=8)
        with self.assertRaisesRegex(PermissionError, "BILATERAL_AUTHORITY_EXPIRED_OR_REORDERED"):
            self.accept.accept(self.command(r), at=self.now+timedelta(seconds=10))
        self.assertFalse(self.contracts._utts)

    def test_07_revoked_receiver_key_blocks_plan(self):
        contract = self.accept_valid().contract
        self.keys.revoke("receiver", reason="SYNTHETIC-COMPROMISE", revoked_at=self.now+timedelta(seconds=11))
        with self.assertRaisesRegex(PermissionError, "BILATERAL_SIGNATURE_INVALID"):
            self.plan.build_plan(utt_id=contract.utt_id, candidates=(self.route(),),
                                 at=self.now+timedelta(seconds=12))
        with self.assertRaises(LookupError):
            self.executions.require_plan_for_utt(contract.utt_id)
        self.assertEqual(self.audit.events[-1]["operation"], "PLAN")

    def test_08_mutated_persisted_etk_blocks_rtt_after_plan(self):
        contract = self.accept_valid().contract
        self.plan.build_plan(utt_id=contract.utt_id, candidates=(self.route(),),
                             at=self.now+timedelta(seconds=11))
        bad = SignatureEnvelope(contract.sender_authority.protected,
                                {**contract.sender_authority.payload, "amount_minor": 1},
                                contract.sender_authority.signature)
        self.contracts._contracts[contract.utt_id] = replace(contract, sender_authority=bad)
        with self.assertRaisesRegex(PermissionError, "BILATERAL_SIGNATURE_INVALID"):
            self.attempt.start_next(utt_id=contract.utt_id, at=self.now+timedelta(seconds=12))
        plan = self.executions.require_plan_for_utt(contract.utt_id)
        self.assertIsNone(plan.current_rtt_id)
        self.assertEqual(plan.attempts_used, 0)
        self.assertEqual(self.audit.events[-1]["operation"], "RTT_CREATE")

    def test_09_route_endpoint_substitution_not_eligible(self):
        contract = self.accept_valid().contract
        with self.assertRaises(NoEligibleRouteError):
            self.plan.build_plan(utt_id=contract.utt_id,
                                 candidates=(self.route(destination="ATTACKER-BANK"),),
                                 at=self.now+timedelta(seconds=11))
        with self.assertRaises(LookupError):
            self.executions.require_plan_for_utt(contract.utt_id)

    def test_10_bilateral_authority_expiration_blocks_new_rtt(self):
        contract = self.accept_valid().contract
        self.plan.build_plan(utt_id=contract.utt_id, candidates=(self.route(),),
                             at=self.now+timedelta(seconds=11))
        with self.assertRaisesRegex(PermissionError, "BILATERAL_AUTHORITY_EXPIRED_OR_REORDERED"):
            self.attempt.start_next(utt_id=contract.utt_id,
                                    at=self.now+timedelta(seconds=181))
        self.assertIsNone(self.executions.require_plan_for_utt(contract.utt_id).current_rtt_id)

    def test_11_gateway_preflight_denial_produces_redacted_event(self):
        recorder = Recorder()
        snapshot = Mock()
        snapshot.load.side_effect = PermissionError("SENDER_FIRST_BILATERAL_V3_REQUIRED")
        gateway = InstitutionalDispatchAdmissionGateway(
            registry=Mock(), wrapper_store=Mock(), wrapper_verifier=Mock(),
            snapshot_reader=snapshot, fence_reader=Mock(), security_audit=recorder,
        )
        with self.assertRaisesRegex(PermissionError, "SENDER_FIRST_BILATERAL_V3_REQUIRED"):
            gateway.preflight(rtt_id="RTT-ATTACK", at=self.now)
        self.assertEqual(recorder.events, [{
            "event_type": "INSTITUTION_DISPATCH_REJECTED", "operation": "PREFLIGHT",
            "correlation_ref": "RTT-ATTACK", "reason_code": "SENDER_FIRST_BILATERAL_V3_REQUIRED",
            "outcome": "DENIED",
        }])

    def test_12_compromised_adapter_cannot_redirect_resolved_beneficiary(self):
        # Exercise the REAL institutional admission verifier using a valid
        # pre-signed wrapper and then substituting a protected account endpoint.
        import tests.test_institution_admission_gateway as fixtures
        other = fixtures.InstitutionalAdmissionGatewayTests("test_signed_wrapper_and_verified_adapter_are_admitted")
        other.setUp()
        recorder = Recorder()
        gateway = InstitutionalDispatchAdmissionGateway(
            registry=other.registry, wrapper_store=other.wrappers,
            wrapper_verifier=other.wrapper_service,
            snapshot_reader=other.reader, fence_reader=other.fence,
            security_audit=recorder,
        )
        mutated = replace(other.request, beneficiary_account_reference="ATTACKER-ACCOUNT")
        with self.assertRaisesRegex(PermissionError, "PROVIDER_REQUEST_DIGEST_MISMATCH"):
            gateway.admit(mutated, at=fixtures.NOW)
        self.assertEqual(other.fence.calls, 0)
        self.assertEqual(other.fence.reservations, [])
        self.assertEqual(recorder.events[0]["event_type"], "INSTITUTION_DISPATCH_REJECTED")
        self.assertEqual(recorder.events[0]["reason_code"], "PROVIDER_REQUEST_DIGEST_MISMATCH")
        self.assertNotIn("ATTACKER-ACCOUNT", str(recorder.events))

    def test_13_unknown_provider_outcome_must_keep_economic_hold(self):
        from tests.test_durable_economic_fencing import (
            FakeDatabase, EconomicFenceTests, NOW,
        )
        scenario = EconomicFenceTests("test_provider_acceptance_is_not_release")
        scenario.setUp()
        db = FakeDatabase(selected=({"fence_epoch": 1},))
        scenario.fence(db).record_provider_outcome(
            utt_id="UTT-TEST", rtt_id="RTT-TEST", outcome="UNKNOWN", at=NOW,
        )
        statements = [query for query, _ in db._cursor.executed]
        self.assertTrue(any("rtt_operational_fences" in query for query in statements))
        self.assertFalse(any("SET state='OPEN'" in query for query in statements))
        self.assertEqual(db.commits, 1)

    def test_14_non_idempotent_crash_never_redispatches(self):
        from tests.test_provider_operations import (
            ProviderOperationsTests, FakeProviderAdapter, ProviderSubmissionState,
        )
        fixture = ProviderOperationsTests("test_non_idempotent_dispatch_recovery_blocks_a_second_provider_call")
        fixture.setUp()
        prepared, _ = fixture.coordinator.prepare(
            rtt_id=fixture.rtt_id, at=fixture.now + timedelta(seconds=22),
        )
        fixture.operations._submissions_by_rtt[fixture.rtt_id] = replace(
            prepared, state=ProviderSubmissionState.DISPATCHING,
            dispatch_attempts=1, version=prepared.version + 1,
            updated_at=fixture.now + timedelta(seconds=22),
        )
        adapter = FakeProviderAdapter(supports_idempotency=False)
        record = fixture.coordinator.dispatch(
            rtt_id=fixture.rtt_id, adapter=adapter,
            at=fixture.now + timedelta(seconds=23),
        )
        self.assertEqual(record.state, ProviderSubmissionState.UNKNOWN)
        self.assertEqual(record.normalized_code, "NON_IDEMPOTENT_RECOVERY_BLOCKED")
        self.assertEqual(adapter.calls, 0)

    def test_15_receiver_consent_without_sender_signature_cannot_mint_utt(self):
        command = replace(self.command(self.receiver()), sender_authority=None)
        with self.assertRaisesRegex(PermissionError, "BILATERAL_P2P_AUTHORITIES_REQUIRED"):
            self.accept.accept(command, at=self.now+timedelta(seconds=10))
        self.assertEqual(self.audit.events[-1]["reason_code"], "BILATERAL_P2P_AUTHORITIES_REQUIRED")
        self.assertEqual(len(self.contracts._utts), 0)

    def test_16_rogue_valid_signer_cannot_claim_sender_authority(self):
        receiver = self.receiver()
        sender = self.sender()
        forged = self.signatures.sign_artifact(
            artifact_type=ArtifactType.ETK_S, payload=sender.payload,
            key_id="rogue", issued_at=self.now+timedelta(seconds=7),
        )
        with self.assertRaisesRegex(PermissionError, "BILATERAL_SIGNER_OWNER_MISMATCH"):
            self.accept.accept(self.command(receiver, sender=forged),
                               at=self.now+timedelta(seconds=10))
        self.assertEqual(len(self.contracts._utts), 0)

    def test_17_receiver_must_bind_exact_existing_sender_etk(self):
        # Two legitimate independently signed sender intents: a receiver
        # approving one cannot authorize the other.
        original = self.sender()
        changed_sender = self.bilateral.issue_sender_authority(
            signed_quote=self.quote, signing_key_id="sender",
            authorized_at=self.now+timedelta(seconds=6),
            expires_at=self.now+timedelta(seconds=180),
        )
        receiver = self.receiver(original)
        with self.assertRaisesRegex(PermissionError, "BILATERAL_CHAIN_BROKEN"):
            self.bilateral.verify_receiver(
                signed_quote=self.quote, sender=changed_sender,
                receiver=receiver, at=self.now+timedelta(seconds=10),
            )
        self.assertFalse(self.contracts._utts)

    def test_18_receiver_cannot_precede_sender(self):
        sender = self.sender()
        with self.assertRaisesRegex(PermissionError, "SENDER_AUTHORITY_NOT_ACTIVE"):
            self.bilateral.issue_receiver_acceptance(
                signed_quote=self.quote, sender=sender, signing_key_id="receiver",
                accepted_at=self.now+timedelta(seconds=4),
                expires_at=self.now+timedelta(seconds=90),
            )
        self.assertFalse(self.contracts._utts)

    def test_19_sender_signature_required_before_receiver_acceptance(self):
        sender = self.sender()
        forged = SignatureEnvelope(sender.protected, {**sender.payload, "amount_minor": 1}, sender.signature)
        with self.assertRaisesRegex(PermissionError, "BILATERAL_SIGNATURE_INVALID"):
            self.receiver(forged)
        self.assertFalse(self.contracts._utts)

    def test_20_receiver_binding_substitution_denied_during_acceptance(self):
        original = self.sender()
        receiver = self.receiver(original)
        other_quote = self.make_quote(replace(self.terms, request_id="REQ-NEW", amount_minor=130000))
        another_sender = self.sender(quote=other_quote)
        with self.assertRaisesRegex(PermissionError, "SENDER_QUOTE_BINDING_MISMATCH"):
            self.accept.accept(self.command(receiver, sender=another_sender),
                               at=self.now+timedelta(seconds=10))
        self.assertFalse(self.contracts._utts)


if __name__ == "__main__":
    unittest.main()
