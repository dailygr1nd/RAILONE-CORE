from __future__ import annotations

import ssl
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

from railone_crypto import InMemoryEd25519KeyProvider, KeyPurpose, SignatureService
from railone_institutions import (
    AdapterEligibilityQuery,
    CapabilityManifestSigner,
    InstitutionAdapterBridge,
    InstitutionAdapterRegistry,
    InstitutionExecutionInstruction,
)
from railone_institutions.auth import SimulationNoAuth
from railone_institutions.codecs import CanonicalJsonCodec, Iso20022Pain001Codec
from railone_institutions.conformance import assert_adapter_submission_conformance
from railone_institutions.generic import (
    ExplicitOutcomeNormalizer,
    GenericHttpAdapterConfig,
    GenericHttpInstitutionAdapter,
)
from railone_institutions.models import (
    AdapterCertificationStatus,
    AdapterEnvironment,
    FinalityLevel,
    InstitutionAuthProfile,
    InstitutionOperation,
    InstitutionOutcome,
    SignedCapabilityManifest,
)
from railone_institutions.reference import (
    DOMESTIC_BANK_PROFILE,
    ReferenceInstitutionAdapter,
    reference_manifest,
)
from railone_institutions.transport import (
    InstitutionHttpResponse,
    InstitutionTransportError,
    UrllibInstitutionTransport,
)
from railone_operations import ProviderExecutionRequest, ProviderOutcome


NOW = datetime(2026, 7, 14, 10, 0, tzinfo=timezone.utc)


def manifest(*, now=NOW, status=AdapterCertificationStatus.CONFORMANCE):
    value = reference_manifest(
        DOMESTIC_BANK_PROFILE,
        source_institution_ids=("INST-SOURCE",),
        destination_institution_ids=("INST-DEST",),
        now=now,
    )
    if status is not value.descriptor.certification_status:
        value = replace(value, descriptor=replace(value.descriptor, certification_status=status))
    return value


def instruction(**overrides):
    values = {
        "idempotency_key": "R1IDEM-001",
        "request_sha256": "a" * 64,
        "utt_id": "UTT-001",
        "rtt_id": "RTT-001",
        "attempt_number": 1,
        "provider_id": "BANK-REFERENCE",
        "adapter_binding_ref": "railone.reference.domestic-bank@1.0.0",
        "rail": "DOMESTIC_BANK",
        "amount_minor": 25_000,
        "currency_from": "KES",
        "receive_amount_minor": 25_000,
        "currency_to": "KES",
        "source_institution_id": "INST-SOURCE",
        "destination_institution_id": "INST-DEST",
        "payer_account_reference": "payer<&secret",
        "beneficiary_account_reference": "receiver<&secret",
    }
    values.update(overrides)
    return InstitutionExecutionInstruction(**values)


def http_manifest():
    value = manifest()
    return replace(
        value,
        operations=(InstitutionOperation.SUBMIT, InstitutionOperation.STATUS_QUERY),
        supports_reconciliation=False,
    )


def provider_request(**overrides):
    item = instruction(**overrides)
    return ProviderExecutionRequest(**{
        name: getattr(item, name) for name in ProviderExecutionRequest.__dataclass_fields__
    })


class QueueTransport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def send(self, request):
        self.requests.append(request)
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


class InstitutionAdapterSpiTests(unittest.TestCase):
    def setUp(self):
        keys = InMemoryEd25519KeyProvider()
        keys.generate(
            key_id="institution-manifest-key",
            owner_id="RAILONE",
            purpose=KeyPurpose.EXECUTION_SIGNING,
            not_before=NOW - timedelta(days=365),
            not_after=NOW + timedelta(days=365),
        )
        self.signer = CapabilityManifestSigner(
            SignatureService(keys), signing_key_id="institution-manifest-key"
        )

    def test_manifest_is_ed25519_signed_and_tamper_evident(self):
        original = manifest()
        signed = self.signer.sign(original, issued_at=NOW)
        self.signer.verify(signed)
        tampered = replace(original, max_amount_minor=original.max_amount_minor - 1)
        with self.assertRaises(PermissionError):
            self.signer.verify(SignedCapabilityManifest(tampered, signed.signature))

    def test_registry_resolves_only_exact_signed_active_version(self):
        item = manifest()
        adapter = ReferenceInstitutionAdapter(item)
        registry = InstitutionAdapterRegistry(self.signer)
        registry.register(adapter, self.signer.sign(item, issued_at=NOW))
        self.assertIs(registry.resolve(item.descriptor.binding_ref, at=NOW), adapter)
        self.assertEqual(
            registry.provider_bridge(item.descriptor.binding_ref, at=NOW).binding_ref,
            item.descriptor.binding_ref,
        )
        with self.assertRaises(KeyError):
            registry.resolve("railone.reference.domestic-bank@1.0.1", at=NOW)

    def test_registry_filters_capabilities_before_route_planning(self):
        item = manifest()
        adapter = ReferenceInstitutionAdapter(item)
        registry = InstitutionAdapterRegistry(self.signer)
        registry.register(adapter, self.signer.sign(item, issued_at=NOW))
        query = AdapterEligibilityQuery(
            "INST-SOURCE", "INST-DEST", "KE", "KE", "DOMESTIC_BANK",
            "KES", "KES", 25_000,
        )
        self.assertEqual(registry.eligible(query, at=NOW), (adapter,))
        self.assertEqual(registry.eligible(replace(query, amount_minor=200_000_000_00), at=NOW), ())

    def test_draft_and_expired_manifests_cannot_execute(self):
        for item, instant in (
            (manifest(status=AdapterCertificationStatus.DRAFT), NOW),
            (manifest(now=NOW - timedelta(days=40)), NOW),
        ):
            registry = InstitutionAdapterRegistry(self.signer)
            adapter = ReferenceInstitutionAdapter(item)
            registry.register(adapter, self.signer.sign(item, issued_at=item.issued_at))
            with self.assertRaises(PermissionError):
                registry.resolve(item.descriptor.binding_ref, at=instant)

    def test_reference_adapter_is_idempotent_and_settlement_is_separate(self):
        adapter = ReferenceInstitutionAdapter(manifest())
        first = adapter.submit(instruction())
        second = adapter.submit(instruction())
        self.assertEqual(first, second)
        self.assertEqual(first.outcome, InstitutionOutcome.ACCEPTED_FOR_PROCESSING)
        self.assertEqual(first.finality, FinalityLevel.PROCESSING)
        self.assertEqual(adapter.query_status(external_reference=first.external_reference).outcome, InstitutionOutcome.PENDING)
        adapter.confirm_settlement(first.external_reference, at=NOW)
        settled = adapter.query_status(external_reference=first.external_reference)
        self.assertEqual((settled.outcome, settled.finality), (InstitutionOutcome.CONFIRMED_SUCCESS, FinalityLevel.SETTLED))

    def test_conformance_suite_checks_stable_idempotent_acceptance(self):
        assert_adapter_submission_conformance(ReferenceInstitutionAdapter(manifest()), instruction())

    def test_bridge_maps_processing_acceptance_and_enforces_rtt_adapter_pin(self):
        bridge = InstitutionAdapterBridge(ReferenceInstitutionAdapter(manifest()))
        result = bridge.submit(provider_request())
        self.assertEqual(result.outcome, ProviderOutcome.ACCEPTED)
        with self.assertRaises(ValueError):
            bridge.submit(provider_request(adapter_binding_ref="another@1.0.0"))

    def test_json_codec_is_deterministic_and_repr_hides_account_references(self):
        codec = CanonicalJsonCodec()
        self.assertEqual(codec.encode_submission(instruction()), codec.encode_submission(instruction()))
        rendered = repr(instruction())
        self.assertNotIn("payer<&secret", rendered)
        self.assertNotIn("receiver<&secret", rendered)

    def test_iso20022_codec_escapes_values_and_is_well_formed(self):
        body = Iso20022Pain001Codec().encode_submission(instruction())
        ET.fromstring(body)
        self.assertIn(b"payer&lt;&amp;secret", body)
        self.assertIn(b"pain.001.001.09", body)

    def test_generic_http_adapter_never_infers_settlement_from_202(self):
        transport = QueueTransport(InstitutionHttpResponse(202, {}, b'{"status":"QUEUED","reference":"EXT-1"}'))
        adapter = GenericHttpInstitutionAdapter(
            descriptor=http_manifest().descriptor,
            manifest=http_manifest(),
            config=GenericHttpAdapterConfig("https://bank.test/payments", "https://bank.test/payments/{reference}", 10),
            codec=CanonicalJsonCodec(),
            auth=SimulationNoAuth(AdapterEnvironment.SANDBOX),
            transport=transport,
            normalizer=ExplicitOutcomeNormalizer(
                submission_codes={"QUEUED": InstitutionOutcome.ACCEPTED_FOR_PROCESSING},
                status_codes={"SETTLED": (InstitutionOutcome.CONFIRMED_SUCCESS, FinalityLevel.SETTLED)},
            ),
        )
        result = adapter.submit(instruction())
        self.assertEqual((result.outcome, result.finality), (InstitutionOutcome.ACCEPTED_FOR_PROCESSING, FinalityLevel.PROCESSING))

    def test_transport_failure_after_dispatch_is_unknown_not_retryable(self):
        transport = QueueTransport(InstitutionTransportError("timeout"))
        adapter = GenericHttpInstitutionAdapter(
            descriptor=http_manifest().descriptor,
            manifest=http_manifest(),
            config=GenericHttpAdapterConfig("https://bank.test/payments", "https://bank.test/payments/{reference}", 10),
            codec=CanonicalJsonCodec(), auth=SimulationNoAuth(AdapterEnvironment.SANDBOX), transport=transport,
            normalizer=ExplicitOutcomeNormalizer(submission_codes={}, status_codes={}),
        )
        self.assertEqual(adapter.submit(instruction()).outcome, InstitutionOutcome.OUTCOME_UNKNOWN)

    def test_non_sandbox_no_auth_and_non_https_transport_fail_closed(self):
        with self.assertRaises(ValueError):
            SimulationNoAuth(AdapterEnvironment.PILOT)
        transport = UrllibInstitutionTransport(
            ssl_context=ssl.create_default_context(), allowed_hosts=frozenset({"bank.test"})
        )
        from railone_institutions.transport import InstitutionHttpRequest
        with self.assertRaises(ValueError):
            transport.send(InstitutionHttpRequest("POST", "http://bank.test", body=b"{}"))

    def test_step_11d_migration_has_version_pins_and_append_only_evidence(self):
        sql = (Path(__file__).parents[1] / "migrations/0009_institution_adapter_spi.sql").read_text()
        for marker in (
            "institution_adapter_manifests", "institution_adapter_bindings",
            "institution_adapter_events", "adapter_conformance_records",
            "adapter_version", "reject_institution_manifest_mutation",
        ):
            self.assertIn(marker, sql)


if __name__ == "__main__":
    unittest.main()
