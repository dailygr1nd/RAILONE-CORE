"""Certification report persistence contracts and test implementation."""

from __future__ import annotations

from threading import RLock
from typing import Protocol

from .models import SignedCertificationReport
from .models import CertificationReport, CertificationTrace
from .runner import CertificationSuite
from datetime import datetime


class CertificationReportStore(Protocol):
    def put(self, report: SignedCertificationReport) -> SignedCertificationReport: ...
    def require(self, report_id: str) -> SignedCertificationReport: ...


class InMemoryCertificationReportStore:
    def __init__(self) -> None:
        self._reports: dict[str, SignedCertificationReport] = {}
        self._lock = RLock()

    def put(self, report: SignedCertificationReport) -> SignedCertificationReport:
        with self._lock:
            existing = self._reports.get(report.report.report_id)
            if existing is not None and existing != report:
                raise RuntimeError("certification report immutability conflict")
            self._reports[report.report.report_id] = report
            return report

    def require(self, report_id: str) -> SignedCertificationReport:
        with self._lock:
            try:
                return self._reports[report_id]
            except KeyError as exc:
                raise LookupError("certification report not found") from exc


class InMemoryCertificationRunRecorder:
    def __init__(self) -> None:
        self.runs: dict[str, dict[str, object]] = {}
        self.traces: dict[tuple[str, object], CertificationTrace] = {}
        self._lock = RLock()

    def begin(self, *, run_id: str, adapter_binding_ref: str,
              manifest_payload_sha256: str, suite: CertificationSuite,
              started_at: datetime) -> None:
        material = {
            "adapter_binding_ref": adapter_binding_ref,
            "manifest_payload_sha256": manifest_payload_sha256,
            "suite_id": suite.suite_id,
            "suite_version": suite.suite_version,
            "started_at": started_at,
            "status": "RUNNING",
        }
        with self._lock:
            existing = self.runs.get(run_id)
            if existing is not None and existing != material:
                raise RuntimeError("certification run immutability conflict")
            if existing is not None:
                raise RuntimeError("certification run has already started")
            self.runs[run_id] = material

    def record_trace(self, trace: CertificationTrace) -> None:
        key = (trace.run_id, trace.scenario)
        with self._lock:
            if trace.run_id not in self.runs:
                raise RuntimeError("certification trace has no active run")
            existing = self.traces.get(key)
            if existing is not None and existing != trace:
                raise RuntimeError("certification trace immutability conflict")
            self.traces[key] = trace

    def complete(self, report: CertificationReport) -> None:
        with self._lock:
            run = self.runs.get(report.run_id)
            if run is None or run["status"] != "RUNNING":
                raise RuntimeError("certification run is not active")
            run["status"] = report.status.value
            run["report_id"] = report.report_id
            run["completed_at"] = report.completed_at
