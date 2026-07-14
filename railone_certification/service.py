"""Ed25519 signing and immutable storage of partner certification reports."""

from __future__ import annotations

from datetime import datetime

from railone_crypto.signature_service import ArtifactType, SignatureService

from railone_institutions.manifest import CapabilityManifestSigner
from railone_institutions.models import AdapterCertificationStatus, SignedCapabilityManifest

from .models import (
    CertificationReport, EvidenceClassification, SignedCertificationReport,
)
from .runner import (
    CertificationRunRecorder, CertificationRunner, CertificationSuite,
    PartnerCertificationDriver,
)
from .store import CertificationReportStore


class CertificationReportService:
    def __init__(
        self, *, signatures: SignatureService, signing_key_id: str,
        store: CertificationReportStore,
    ) -> None:
        self._signatures = signatures
        self._key_id = signing_key_id
        self._store = store

    def sign_and_commit(
        self, report: CertificationReport, *, at: datetime | None = None
    ) -> SignedCertificationReport:
        if report.evidence_classification is EvidenceClassification.SYNTHETIC_SELF_TEST:
            raise PermissionError("synthetic self-test reports cannot be signed as partner evidence")
        envelope = self._signatures.sign_artifact(
            artifact_type=ArtifactType.PARTNER_CERTIFICATION_REPORT,
            payload=report.to_payload(), key_id=self._key_id, issued_at=at,
        )
        return self._store.put(SignedCertificationReport(report, envelope))

    def verify(self, signed: SignedCertificationReport) -> None:
        result = self._signatures.verify_artifact(
            signed.signature,
            expected_artifact_type=ArtifactType.PARTNER_CERTIFICATION_REPORT,
        )
        if not result.valid:
            raise PermissionError(f"certification report rejected: {result.reason}")
        if signed.signature.to_dict()["payload"] != signed.report.to_payload():
            raise PermissionError("certification report object differs from signed payload")


class PartnerCertificationCoordinator:
    """Only authoritative path from a verified manifest to a signed report."""

    def __init__(
        self, *, manifest_verifier: CapabilityManifestSigner,
        runner: CertificationRunner, recorder: CertificationRunRecorder,
        reports: CertificationReportService,
    ) -> None:
        self._manifests = manifest_verifier
        self._runner = runner
        self._recorder = recorder
        self._reports = reports

    def certify(
        self, *, run_id: str, driver: PartnerCertificationDriver,
        signed_manifest: SignedCapabilityManifest, at: datetime | None = None,
    ) -> SignedCertificationReport:
        self._manifests.verify(signed_manifest)
        manifest = signed_manifest.manifest
        instant = at or datetime.now(manifest.issued_at.tzinfo)
        if not manifest.is_active_at(instant):
            raise PermissionError("inactive adapter manifest cannot be certified")
        if manifest.descriptor.certification_status not in {
            AdapterCertificationStatus.CONFORMANCE,
            AdapterCertificationStatus.CERTIFIED,
        }:
            raise PermissionError("adapter manifest is not eligible for certification")
        if driver.adapter_binding_ref != manifest.descriptor.binding_ref:
            raise PermissionError("certification driver does not match the signed adapter version")
        if driver.evidence_classification is not EvidenceClassification.PARTNER_SANDBOX:
            raise PermissionError("authoritative certification requires partner sandbox evidence")
        report = self._runner.run(
            run_id=run_id, driver=driver,
            manifest_payload_sha256=str(
                signed_manifest.signature.protected["payload_sha256"]
            ),
            suite=CertificationSuite.for_manifest(manifest), at=instant,
            recorder=self._recorder,
        )
        return self._reports.sign_and_commit(report, at=report.completed_at)
