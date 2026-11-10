"""Admission gateway fails closed in institutional sandbox and preserves pilot behavior."""
from __future__ import annotations

import copy
import unittest
from dataclasses import replace
from datetime import timedelta

from railone_crypto import InMemoryEd25519KeyProvider, KeyPurpose, SignatureService
from railone_institutions import (
    CapabilityManifestSigner, InstitutionAdapterRegistry,
    InstitutionalDispatchAdmissionGateway,
)
from railone_institutions.reference import (
    CROSS_BORDER_PROFILE, ReferenceInstitutionAdapter, reference_manifest,
)
from railone_institutions.wrapper import (
    CanonicalDispatchWrapper, DispatchWrapperService,
)
from railone_institutions.wrapper_store import InMemoryDispatchWrapperStore
from railone_operations import ProviderExecutionRequest, ProviderSubmissionCoordinator
from tests.test_institution_dispatch_wrapper import NOW, sections, snapshot


class TrustedReader:
    def __init__(self, expected):
        self.expected = expected

    def load(self, *, rtt_id):
        if rtt_id != self.expected.rtt_id:
            raise LookupError("unknown RTT in trusted state")
        return self.expected


class FixedFence:
    """Test-only stand-in for an independently verified durable fence."""
    def __init__(self, *, epoch=1):
        self.epoch = epoch
        self.calls = 0
        self.reservations = []
        self.outcomes = []

    def reserve_dispatch(self, *, utt_id, rtt_id, fence_epoch,
                         release_evidence_ref, request_sha256, at):
        self.reservations.append((utt_id, rtt_id, fence_epoch, request_sha256))

    def record_provider_outcome(self, *, utt_id, rtt_id, outcome, at):
        self.outcomes.append((utt_id, rtt_id, outcome))

    def assert_dispatch_safe(self, *, utt_id, rtt_id, fence_epoch, release_evidence_ref, at):
        self.calls += 1
        if fence_epoch != self.epoch or release_evidence_ref is not None:
            raise PermissionError("economic-effect fence was not safely released")


def provider_request(body, **overrides):
    trace, binding, terms = body["trace_identifiers"], body["execution_binding"], body["commercial_terms"]
    data = dict(
        idempotency_key=binding["idempotency_key"],
        request_sha256=binding["request_sha256"],
        utt_id=trace["utt_id"], rtt_id=trace["rtt_id"], attempt_number=trace["attempt_number"],
        provider_id=binding["provider_id"], adapter_binding_ref=binding["adapter_binding_ref"],
        rail="CROSS_BORDER", amount_minor=terms["source_amount_minor"],
        currency_from=terms["source_currency"], receive_amount_minor=terms["receive_amount_minor"],
        currency_to=terms["receive_currency"],
        source_institution_id="INST-SOURCE", destination_institution_id="INST-DEST",
        payer_account_reference="PRIVATE-SENDER", beneficiary_account_reference="PRIVATE-RECEIVER",
    )
    data.update(overrides)
    return ProviderExecutionRequest(**data)


class InstitutionalAdmissionGatewayTests(unittest.TestCase):
    def setUp(self):
        keys = InMemoryEd25519KeyProvider()
        keys.generate(
            key_id="phase4-test", owner_id="RAILONE", purpose=KeyPurpose.EXECUTION_SIGNING,
            not_before=NOW - timedelta(days=1), not_after=NOW + timedelta(days=1),
        )
        signatures = SignatureService(keys)
        self.wrapper_service = DispatchWrapperService(signatures, signing_key_id="phase4-test")
        self.manifest_signer = CapabilityManifestSigner(signatures, signing_key_id="phase4-test")
        self.profile = replace(
            CROSS_BORDER_PROFILE, adapter_id="synthetic.mtn-crdb", provider_id="SYN-UG-TZ-PROVIDER",
            rails=("CROSS_BORDER",), currencies_from=("UGX",), currencies_to=("TZS",),
            source_countries=("UG",), destination_countries=("TZ",),
        )
        self.manifest = reference_manifest(
            self.profile, source_institution_ids=("INST-SOURCE",),
            destination_institution_ids=("INST-DEST",), now=NOW,
        )
        self.adapter = ReferenceInstitutionAdapter(self.manifest)
        self.registry = InstitutionAdapterRegistry(self.manifest_signer)
        signed_manifest = self.manifest_signer.sign(self.manifest, issued_at=NOW)
        self.registry.register(self.adapter, signed_manifest)
        body_sections = sections()
        body_sections["execution_binding"]["adapter_manifest_digest"] = signed_manifest.signature.protected["payload_sha256"]
        self.wrapper = CanonicalDispatchWrapper.build(
            issued_at_epoch=int(NOW.timestamp()), expires_at_epoch=int(NOW.timestamp()) + 30,
            **body_sections,
        )
        self.expected = snapshot(self.wrapper.to_payload())
        self.wrappers = InMemoryDispatchWrapperStore(self.wrapper_service)
        signed = self.wrapper_service.issue(self.wrapper, expected=self.expected, at=NOW)
        self.wrappers.put(signed, expected=self.expected, at=NOW)
        self.fence = FixedFence()
        self.reader = TrustedReader(self.expected)
        self.gateway = InstitutionalDispatchAdmissionGateway(
            registry=self.registry, wrapper_store=self.wrappers,
            wrapper_verifier=self.wrapper_service, snapshot_reader=self.reader,
            fence_reader=self.fence,
        )
        self.request = provider_request(self.wrapper.to_payload())

    def test_signed_wrapper_and_verified_adapter_are_admitted(self):
        bridge = self.gateway.admit(self.request, at=NOW)
        self.assertEqual(bridge.binding_ref, "synthetic.mtn-crdb@1.0.0")
        self.assertEqual(self.fence.calls, 1)
        self.assertEqual(len(self.fence.reservations), 1)
        # Return value is the registry-selected adapter; submission remains processing-only.
        self.assertEqual(bridge.provider_id, self.request.provider_id)

    def test_expired_wrapper_rejected_before_fence_or_adapter_dispatch(self):
        with self.assertRaises(PermissionError):
            self.gateway.admit(self.request, at=NOW + timedelta(seconds=31))
        self.assertEqual(self.fence.calls, 0)

    def test_tampered_provider_values_rejected(self):
        for field, value in (("request_sha256", "1" * 64), ("amount_minor", 1),
                             ("adapter_binding_ref", "foreign@1.0.0"),
                             ("idempotency_key", "DIFFERENT")):
            with self.subTest(field=field), self.assertRaises(PermissionError):
                self.gateway.admit(replace(self.request, **{field: value}), at=NOW)
        self.assertEqual(self.fence.calls, 0)

    def test_stale_or_unproven_economic_fence_rejected(self):
        self.fence.epoch = 2
        with self.assertRaises(PermissionError):
            self.gateway.admit(self.request, at=NOW)

    def test_wrong_expected_snapshot_rejected(self):
        self.reader.expected = replace(self.expected, request_sha256="9" * 64)
        with self.assertRaises(PermissionError):
            self.gateway.admit(self.request, at=NOW)

    def test_manifest_changed_since_wrapper_is_rejected(self):
        # A different valid manifest cannot silently replace the original digest.
        self.registry = InstitutionAdapterRegistry(self.manifest_signer)
        other = replace(self.manifest, max_amount_minor=self.manifest.max_amount_minor - 1)
        self.registry.register(ReferenceInstitutionAdapter(other), self.manifest_signer.sign(other, issued_at=NOW))
        self.gateway = InstitutionalDispatchAdmissionGateway(
            registry=self.registry, wrapper_store=self.wrappers,
            wrapper_verifier=self.wrapper_service, snapshot_reader=self.reader,
            fence_reader=self.fence,
        )
        with self.assertRaises(PermissionError):
            self.gateway.admit(self.request, at=NOW)

    def test_unsupported_institution_or_rail_rejected(self):
        for field, value in (("source_institution_id", "UNREGISTERED"), ("rail", "UNSUPPORTED")):
            with self.subTest(field=field), self.assertRaises(PermissionError):
                self.gateway.admit(replace(self.request, **{field: value}), at=NOW)

    def test_unknown_adapter_binding_rejected(self):
        self.registry = InstitutionAdapterRegistry(self.manifest_signer)
        self.gateway = InstitutionalDispatchAdmissionGateway(
            registry=self.registry, wrapper_store=self.wrappers,
            wrapper_verifier=self.wrapper_service, snapshot_reader=self.reader,
            fence_reader=self.fence,
        )
        with self.assertRaises(KeyError):
            self.gateway.admit(self.request, at=NOW)

    def test_missing_wrapper_fails_closed(self):
        self.wrappers = InMemoryDispatchWrapperStore(self.wrapper_service)
        self.gateway = InstitutionalDispatchAdmissionGateway(
            registry=self.registry, wrapper_store=self.wrappers,
            wrapper_verifier=self.wrapper_service, snapshot_reader=self.reader,
            fence_reader=self.fence,
        )
        with self.assertRaises(LookupError):
            self.gateway.admit(self.request, at=NOW)


class InstitutionalCoordinatorBoundaryTests(unittest.TestCase):
    def setUp(self):
        from tests.test_provider_operations import ProviderOperationsTests, FakeProviderAdapter
        self.fixture = ProviderOperationsTests("test_preparation_is_idempotent_and_uses_stable_provider_key")
        self.fixture.setUp()
        self.fake = FakeProviderAdapter()
        self.adapter_factory = FakeProviderAdapter

    def build(self, *, mode="INSTITUTIONAL_SANDBOX", gate=None):
        f = self.fixture
        return ProviderSubmissionCoordinator(
            signatures=f.signatures, contracts=f.contracts, executions=f.executions,
            operations=f.operations, endpoint_resolver=f.endpoint_resolver,
            event_signing_key_id="R1CORE:execution:2026-01",
            dispatch_mode=mode, institutional_admission=gate,
        )

    def test_missing_gate_rejects_institutional_mode(self):
        with self.assertRaises(ValueError):
            self.build()

    def test_live_funds_mode_is_explicitly_disabled(self):
        with self.assertRaises(ValueError):
            self.build(mode="LIVE_FUNDS")

    def test_institutional_mode_rejects_caller_adapter_and_direct_prepare(self):
        from tests.test_provider_operations import FakeProviderAdapter
        class StubGate:
            def preflight(self, *, rtt_id, at):
                pass
            def admit(self, request, *, at):
                return FakeProviderAdapter()
        coordinator = self.build(gate=StubGate())
        with self.assertRaises(PermissionError):
            coordinator.dispatch(rtt_id=self.fixture.rtt_id, adapter=self.fake, at=self.fixture.now + timedelta(seconds=22))
        with self.assertRaises(PermissionError):
            coordinator.prepare(rtt_id=self.fixture.rtt_id, at=self.fixture.now + timedelta(seconds=22))
        self.assertEqual(self.fake.calls, 0)

    def test_institutional_gate_runs_before_provider_effect(self):
        class DenyGate:
            def preflight(self, *, rtt_id, at):
                raise PermissionError("admission rejected")
            def admit(self, request, *, at):
                raise PermissionError("admission rejected")
        coordinator = self.build(gate=DenyGate())
        with self.assertRaises(PermissionError):
            coordinator.dispatch(rtt_id=self.fixture.rtt_id, at=self.fixture.now + timedelta(seconds=22))
        with self.assertRaises(LookupError):
            self.fixture.operations.require_submission(self.fixture.rtt_id)

    def test_institutional_mode_uses_only_gate_selected_adapter(self):
        chosen = self.fake
        class TrustedGate:
            def preflight(self, *, rtt_id, at):
                pass
            def admit(self, request, *, at):
                return chosen
            def record_provider_outcome(self, *, utt_id, rtt_id, outcome, at):
                self.observed = outcome
        coordinator = self.build(gate=TrustedGate())
        record = coordinator.dispatch(
            rtt_id=self.fixture.rtt_id, at=self.fixture.now + timedelta(seconds=22)
        )
        self.assertEqual(record.state.value, "ACCEPTED")
        self.assertEqual(chosen.calls, 1)

    def test_simulated_pilot_still_operates_without_gate(self):
        coordinator = self.build(mode="SIMULATED_PILOT")
        result = coordinator.dispatch(rtt_id=self.fixture.rtt_id, adapter=self.fake, at=self.fixture.now + timedelta(seconds=22))
        self.assertEqual(result.state.value, "ACCEPTED")
        self.assertEqual(self.fake.calls, 1)


if __name__ == "__main__":
    unittest.main()
