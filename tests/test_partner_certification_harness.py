from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from railone_certification import (
    CaseStatus, CertificationReportService, CertificationRunner,
    CertificationScenario, CertificationStatus, CertificationSuite,
    CertificationTrace, CertificationTraceEvaluator, CertificationTraceEvent,
    InMemoryCertificationReportStore, InMemoryCertificationRunRecorder,
    SignedCertificationReport, TraceEventType,
    EvidenceClassification, PartnerCertificationCoordinator,
)
from railone_certification.cli import main as certification_cli
from railone_certification.codec import load_trace_json, report_from_payload
from railone_certification.reference import SyntheticReferenceCertificationDriver
from railone_crypto import InMemoryEd25519KeyProvider, KeyPurpose, SignatureService
from railone_crypto.signature_service import ArtifactType
from railone_institutions.models import FinalityLevel, InstitutionOperation
from railone_institutions.manifest import CapabilityManifestSigner
from railone_institutions.reference import (
    CROSS_BORDER_PROFILE, DOMESTIC_BANK_PROFILE, reference_manifest,
)


NOW = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)
BINDING = "railone.reference.certification@1.0.0"


class RaisingDriver:
    adapter_binding_ref = BINDING
    evidence_classification = EvidenceClassification.PARTNER_SANDBOX

    def execute_case(self, **_):
        raise TimeoutError("provider-secret-must-not-leak")


class PartnerSandboxDriver(SyntheticReferenceCertificationDriver):
    def __init__(self, adapter_binding_ref=BINDING):
        super().__init__(adapter_binding_ref)
        self.evidence_classification = EvidenceClassification.PARTNER_SANDBOX


def runner(driver=None, *, run_id="RUN-CERT-001", suite=None):
    return CertificationRunner().run(
        run_id=run_id,
        driver=driver or SyntheticReferenceCertificationDriver(BINDING),
        manifest_payload_sha256="a" * 64,
        suite=suite or CertificationSuite.pilot_v1(),
        at=NOW,
    )


class PartnerCertificationHarnessTests(unittest.TestCase):
    def test_comprehensive_synthetic_self_test_passes_all_eleven_cases(self):
        report = runner()

        self.assertEqual(report.status, CertificationStatus.PASSED)
        self.assertEqual(len(report.cases), 11)
        self.assertTrue(all(case.status is CaseStatus.PASSED for case in report.cases))

    def test_trace_content_ids_reject_event_tampering(self):
        trace = SyntheticReferenceCertificationDriver(BINDING).execute_case(
            run_id="RUN-1", scenario=CertificationScenario.P2P_SETTLED
        )
        with self.assertRaisesRegex(ValueError, "content identifier"):
            replace(trace.events[0], event_type=TraceEventType.PLAN_FINALIZED)

    def test_evaluator_rejects_blind_redispatch_after_unknown_outcome(self):
        original = SyntheticReferenceCertificationDriver(BINDING).execute_case(
            run_id="RUN-2", scenario=CertificationScenario.UNKNOWN_THEN_RECONCILED
        )
        rows = list(original.events)
        rows.insert(4, CertificationTraceEvent.create(
            scenario=original.scenario,
            event_type=TraceEventType.PROVIDER_DISPATCHED,
            occurred_at=rows[3].occurred_at,
            sequence=5,
            adapter_binding_ref=BINDING,
            utt_id=rows[3].utt_id, rtt_id=rows[3].rtt_id,
        ))
        rebuilt = tuple(
            CertificationTraceEvent.create(
                scenario=event.scenario, event_type=event.event_type,
                occurred_at=event.occurred_at + timedelta(microseconds=index),
                sequence=index, adapter_binding_ref=event.adapter_binding_ref,
                utt_id=event.utt_id, rtt_id=event.rtt_id,
                evidence_sha256=event.evidence_sha256,
                metadata=dict(event.metadata),
            )
            for index, event in enumerate(rows, start=1)
        )
        trace = CertificationTrace.create(
            run_id=original.run_id, scenario=original.scenario,
            adapter_binding_ref=BINDING, started_at=original.started_at,
            completed_at=rebuilt[-1].occurred_at, events=rebuilt,
        )

        failures = CertificationTraceEvaluator().evaluate(trace)

        self.assertTrue(any("blind redispatch" in failure for failure in failures))

    def test_callback_duplication_produces_one_evidence_and_two_sms_records(self):
        trace = SyntheticReferenceCertificationDriver(BINDING).execute_case(
            run_id="RUN-3",
            scenario=CertificationScenario.DUPLICATE_CALLBACK_EXACTLY_ONCE,
        )
        counts = {kind: sum(event.event_type is kind for event in trace.events) for kind in TraceEventType}
        self.assertEqual(counts[TraceEventType.CALLBACK_ACCEPTED], 2)
        self.assertEqual(counts[TraceEventType.EXTERNAL_EVIDENCE_VERIFIED], 1)
        self.assertEqual(counts[TraceEventType.SMS_PREPARED], 2)
        self.assertEqual(CertificationTraceEvaluator().evaluate(trace), ())

    def test_driver_exception_is_redacted_and_fails_the_report(self):
        suite = CertificationSuite(
            "RAILONE-PARTNER-PILOT", "1.0.0",
            (CertificationScenario.P2P_SETTLED,),
        )
        report = runner(RaisingDriver(), suite=suite)

        self.assertEqual(report.status, CertificationStatus.FAILED)
        self.assertEqual(report.cases[0].status, CaseStatus.ERROR)
        self.assertNotIn("provider-secret", " ".join(report.cases[0].failures))
        self.assertIn("TimeoutError", report.cases[0].failures[0])

    def test_report_is_ed25519_signed_verified_and_stored_immutably(self):
        keys = InMemoryEd25519KeyProvider()
        keys.generate(
            key_id="certification-key", owner_id="RAILONE",
            purpose=KeyPurpose.EXECUTION_SIGNING,
            not_before=NOW - timedelta(days=1), not_after=NOW + timedelta(days=30),
        )
        signatures = SignatureService(keys)
        store = InMemoryCertificationReportStore()
        service = CertificationReportService(
            signatures=signatures, signing_key_id="certification-key", store=store
        )
        report = runner(PartnerSandboxDriver())

        signed = service.sign_and_commit(report, at=NOW + timedelta(minutes=1))
        service.verify(signed)

        self.assertIs(store.require(report.report_id), signed)
        check = signatures.verify_artifact(
            signed.signature,
            expected_artifact_type=ArtifactType.PARTNER_CERTIFICATION_REPORT,
        )
        self.assertTrue(check.valid)
        other = runner(PartnerSandboxDriver(), run_id="RUN-CERT-OTHER")
        with self.assertRaises(PermissionError):
            service.verify(SignedCertificationReport(other, signed.signature))

    def test_authoritative_coordinator_verifies_manifest_and_rejects_synthetic_driver(self):
        keys = InMemoryEd25519KeyProvider()
        keys.generate(
            key_id="execution-key", owner_id="RAILONE",
            purpose=KeyPurpose.EXECUTION_SIGNING,
            not_before=NOW - timedelta(days=1), not_after=NOW + timedelta(days=30),
        )
        signatures = SignatureService(keys)
        manifest_signer = CapabilityManifestSigner(
            signatures, signing_key_id="execution-key"
        )
        item = reference_manifest(
            DOMESTIC_BANK_PROFILE,
            source_institution_ids=("INST-A",), destination_institution_ids=("INST-B",),
            now=NOW,
        )
        signed_manifest = manifest_signer.sign(item, issued_at=NOW)
        reports = CertificationReportService(
            signatures=signatures, signing_key_id="execution-key",
            store=InMemoryCertificationReportStore(),
        )
        recorder = InMemoryCertificationRunRecorder()
        coordinator = PartnerCertificationCoordinator(
            manifest_verifier=manifest_signer,
            runner=CertificationRunner(), recorder=recorder, reports=reports,
        )
        driver = PartnerSandboxDriver(item.descriptor.binding_ref)

        signed = coordinator.certify(
            run_id="RUN-AUTH-001", driver=driver,
            signed_manifest=signed_manifest, at=NOW,
        )

        reports.verify(signed)
        self.assertEqual(
            signed.report.evidence_classification,
            EvidenceClassification.PARTNER_SANDBOX,
        )
        self.assertEqual(recorder.runs["RUN-AUTH-001"]["status"], "PASSED")
        self.assertEqual(
            len([key for key in recorder.traces if key[0] == "RUN-AUTH-001"]),
            len(signed.report.cases),
        )
        with self.assertRaisesRegex(PermissionError, "partner sandbox"):
            coordinator.certify(
                run_id="RUN-SYNTHETIC", driver=SyntheticReferenceCertificationDriver(
                    item.descriptor.binding_ref
                ),
                signed_manifest=signed_manifest, at=NOW,
            )

    def test_report_and_trace_json_round_trip_strictly(self):
        driver = SyntheticReferenceCertificationDriver(BINDING)
        trace = driver.execute_case(
            run_id="RUN-4", scenario=CertificationScenario.HISTORY_ACCESS_CONTROL
        )
        restored_trace = load_trace_json(json.dumps(trace.to_payload()).encode())
        report = runner(run_id="RUN-4")
        restored_report = report_from_payload(report.to_payload())

        self.assertEqual(restored_trace, trace)
        self.assertEqual(restored_report, report)

    def test_metadata_rejects_secret_shaped_noncanonical_fields(self):
        with self.assertRaisesRegex(ValueError, "non-canonical"):
            CertificationTraceEvent.create(
                scenario=CertificationScenario.P2P_SETTLED,
                event_type=TraceEventType.UTT_CREATED,
                occurred_at=NOW, sequence=1, adapter_binding_ref=BINDING,
                metadata={"access_token": "secret"},
            )

    def test_suite_is_capability_aware(self):
        domestic = reference_manifest(
            DOMESTIC_BANK_PROFILE,
            source_institution_ids=("INST-A",), destination_institution_ids=("INST-B",),
            now=NOW,
        )
        cross_border = reference_manifest(
            CROSS_BORDER_PROFILE,
            source_institution_ids=("INST-EG",), destination_institution_ids=("INST-KE",),
            now=NOW,
        )

        domestic_suite = CertificationSuite.for_manifest(domestic)
        cross_suite = CertificationSuite.for_manifest(cross_border)

        self.assertNotIn(CertificationScenario.CROSS_BORDER_SETTLED, domestic_suite.scenarios)
        self.assertIn(CertificationScenario.CROSS_BORDER_SETTLED, cross_suite.scenarios)
        self.assertNotIn(CertificationScenario.TAMPERED_CALLBACK_REJECTED, domestic_suite.scenarios)

    def test_manifest_without_finality_evidence_path_is_not_certifiable(self):
        item = reference_manifest(
            DOMESTIC_BANK_PROFILE,
            source_institution_ids=("INST-A",), destination_institution_ids=("INST-B",),
            now=NOW,
        )
        item = replace(
            item,
            operations=(InstitutionOperation.SUBMIT,),
            supports_active_status=False, supports_reconciliation=False,
            asserted_finality=FinalityLevel.PROCESSING,
        )
        with self.assertRaisesRegex(ValueError, "finality evidence"):
            CertificationSuite.for_manifest(item)

    def test_offline_cli_output_is_explicitly_unsigned(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "draft.json"
            status = certification_cli([
                "--run-id", "RUN-CLI-001",
                "--adapter-binding", BINDING,
                "--manifest-sha256", "b" * 64,
                "--output", str(output),
                "--synthetic-self-test",
            ])
            payload = json.loads(output.read_text())

        self.assertEqual(status, 0)
        self.assertFalse(payload["authoritative"])
        self.assertEqual(payload["classification"], "UNSIGNED_CERTIFICATION_DRAFT")

    def test_step_11e_migration_is_append_only_and_version_pinned(self):
        sql = (Path(__file__).parents[1] / "migrations/0010_partner_certification_harness.sql").read_text()
        for marker in (
            "partner_certification_runs", "partner_certification_traces",
            "partner_certification_reports", "adapter_version",
            "reject_certification_evidence_mutation", "Ed25519",
        ):
            self.assertIn(marker, sql)


if __name__ == "__main__":
    unittest.main()
