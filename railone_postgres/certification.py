"""Append-only PostgreSQL store for signed partner certification reports."""

from __future__ import annotations

from railone_certification.codec import report_from_payload
from railone_certification.models import SignedCertificationReport
from railone_certification.models import CertificationReport, CertificationTrace
from railone_certification.runner import CertificationRunRecorder, CertificationSuite
from railone_crypto.canonical_json import canonical_json_bytes
import hashlib
from datetime import datetime
from railone_certification.store import CertificationReportStore
from railone_crypto.signature_service import SignatureEnvelope

from .codec import json_object, json_text
from .runtime import PostgresDatabase


class PostgresCertificationReportStore(CertificationReportStore):
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    def put(self, signed: SignedCertificationReport) -> SignedCertificationReport:
        report = signed.report
        envelope = signed.signature.to_dict()
        adapter_id, adapter_version = report.adapter_binding_ref.rsplit("@", 1)
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO railone.partner_certification_reports
                   (report_id, run_id, adapter_id, adapter_version, suite_id,
                    suite_version, status, evidence_classification,
                    signed_report, payload_sha256,
                    signing_key_id, issued_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,
                           to_timestamp(%s))
                   ON CONFLICT (report_id) DO NOTHING""",
                (
                    report.report_id, report.run_id, adapter_id, adapter_version,
                    report.suite_id, report.suite_version, report.status.value,
                    report.evidence_classification.value,
                    json_text(envelope), envelope["protected"]["payload_sha256"],
                    envelope["protected"]["kid"], envelope["protected"]["iat"],
                ),
            )
        stored = self.require(report.report_id)
        if stored != signed:
            raise RuntimeError("partner certification report immutability conflict")
        return stored

    def require(self, report_id: str) -> SignedCertificationReport:
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT signed_report FROM railone.partner_certification_reports WHERE report_id=%s",
                (report_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise LookupError("partner certification report not found")
            envelope = SignatureEnvelope.from_dict(json_object(row["signed_report"]))
            return SignedCertificationReport(
                report=report_from_payload(envelope.to_dict()["payload"]),
                signature=envelope,
            )


class PostgresCertificationRunRecorder(CertificationRunRecorder):
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    def begin(self, *, run_id: str, adapter_binding_ref: str,
              manifest_payload_sha256: str, suite: CertificationSuite,
              started_at: datetime) -> None:
        adapter_id, adapter_version = adapter_binding_ref.rsplit("@", 1)
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO railone.partner_certification_runs
                   (run_id, adapter_id, adapter_version, manifest_payload_sha256,
                    suite_id, suite_version, status, started_at)
                   VALUES (%s,%s,%s,%s,%s,%s,'RUNNING',%s)
                   ON CONFLICT (run_id) DO NOTHING""",
                (run_id, adapter_id, adapter_version, manifest_payload_sha256,
                 suite.suite_id, suite.suite_version, started_at),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("certification run already exists")

    def record_trace(self, trace: CertificationTrace) -> None:
        payload = trace.to_payload()
        digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO railone.partner_certification_traces
                   (trace_id, run_id, scenario, adapter_binding_ref,
                    trace_payload, trace_payload_sha256, started_at, completed_at)
                   VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s)
                   ON CONFLICT (trace_id) DO NOTHING""",
                (trace.trace_id, trace.run_id, trace.scenario.value,
                 trace.adapter_binding_ref, json_text(payload), digest,
                 trace.started_at, trace.completed_at),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("certification trace already exists")

    def complete(self, report: CertificationReport) -> None:
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """UPDATE railone.partner_certification_runs
                   SET status=%s, completed_at=%s, version=version+1,
                       updated_at=%s
                   WHERE run_id=%s AND status='RUNNING' AND version=1""",
                (report.status.value, report.completed_at,
                 report.completed_at, report.run_id),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("certification run completion lost compare-and-swap")
