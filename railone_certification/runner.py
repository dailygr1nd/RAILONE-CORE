"""Bounded execution of the mandatory RailOne partner pilot suite."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from railone_institutions.models import InstitutionCapabilityManifest

from .evaluator import CertificationTraceEvaluator
from .models import (
    CaseStatus, CertificationCaseResult, CertificationReport,
    CertificationScenario, CertificationStatus, CertificationTrace,
    EvidenceClassification,
)


@dataclass(frozen=True, slots=True)
class CertificationSuite:
    suite_id: str
    suite_version: str
    scenarios: tuple[CertificationScenario, ...]
    per_case_timeout_seconds: int = 30

    @classmethod
    def pilot_v1(cls) -> "CertificationSuite":
        return cls(
            suite_id="RAILONE-PARTNER-PILOT",
            suite_version="1.0.0",
            scenarios=tuple(CertificationScenario),
        )

    @classmethod
    def for_manifest(cls, manifest: InstitutionCapabilityManifest) -> "CertificationSuite":
        if not (
            manifest.supports_callbacks
            or manifest.supports_active_status
            or manifest.supports_reconciliation
        ):
            raise ValueError("pilot certification requires an external finality evidence path")
        scenarios = [
            CertificationScenario.P2P_SETTLED,
            CertificationScenario.MERCHANT_SUPPLIER_SETTLED,
            CertificationScenario.HISTORY_ACCESS_CONTROL,
            CertificationScenario.SMS_FINALITY_GATE,
            CertificationScenario.ADAPTER_VERSION_PIN,
            CertificationScenario.DUPLICATE_SUBMISSION,
        ]
        cross_border = (
            set(manifest.source_countries) != set(manifest.destination_countries)
            or set(manifest.currencies_from) != set(manifest.currencies_to)
        )
        if cross_border:
            scenarios.append(CertificationScenario.CROSS_BORDER_SETTLED)
        if manifest.supports_active_status or manifest.supports_reconciliation:
            scenarios.append(CertificationScenario.UNKNOWN_THEN_RECONCILED)
        if manifest.supports_callbacks:
            scenarios.extend((
                CertificationScenario.TAMPERED_CALLBACK_REJECTED,
                CertificationScenario.DUPLICATE_CALLBACK_EXACTLY_ONCE,
                CertificationScenario.SETTLEMENT_AMOUNT_MISMATCH_REJECTED,
            ))
        return cls(
            suite_id="RAILONE-PARTNER-PILOT",
            suite_version="1.0.0",
            scenarios=tuple(scenarios),
        )


class PartnerCertificationDriver(Protocol):
    adapter_binding_ref: str
    evidence_classification: EvidenceClassification

    def execute_case(
        self, *, run_id: str, scenario: CertificationScenario
    ) -> CertificationTrace: ...


class CertificationRunRecorder(Protocol):
    def begin(self, *, run_id: str, adapter_binding_ref: str,
              manifest_payload_sha256: str, suite: CertificationSuite,
              started_at: datetime) -> None: ...
    def record_trace(self, trace: CertificationTrace) -> None: ...
    def complete(self, report: CertificationReport) -> None: ...


class CertificationRunner:
    def __init__(self, evaluator: CertificationTraceEvaluator | None = None) -> None:
        self._evaluator = evaluator or CertificationTraceEvaluator()

    def run(
        self,
        *,
        run_id: str,
        driver: PartnerCertificationDriver,
        manifest_payload_sha256: str,
        suite: CertificationSuite | None = None,
        at: datetime | None = None,
        recorder: CertificationRunRecorder | None = None,
    ) -> CertificationReport:
        selected = suite or CertificationSuite.pilot_v1()
        start = (at or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)
        if recorder is not None:
            recorder.begin(
                run_id=run_id, adapter_binding_ref=driver.adapter_binding_ref,
                manifest_payload_sha256=manifest_payload_sha256,
                suite=selected, started_at=start,
            )
        cases: list[CertificationCaseResult] = []
        for scenario in selected.scenarios:
            case_start = time.monotonic()
            try:
                trace = driver.execute_case(run_id=run_id, scenario=scenario)
                if recorder is not None:
                    recorder.record_trace(trace)
                duration_ms = int((time.monotonic() - case_start) * 1000)
                failures = list(self._evaluator.evaluate(trace))
                if trace.run_id != run_id:
                    failures.append("trace run_id does not match certification run")
                if trace.adapter_binding_ref != driver.adapter_binding_ref:
                    failures.append("driver changed adapter binding")
                if duration_ms > selected.per_case_timeout_seconds * 1000:
                    failures.append("certification case exceeded its execution timeout")
                cases.append(CertificationCaseResult(
                    scenario=scenario,
                    status=CaseStatus.FAILED if failures else CaseStatus.PASSED,
                    trace_id=trace.trace_id,
                    failures=tuple(sorted(set(failures))),
                    duration_ms=duration_ms,
                    event_count=len(trace.events),
                ))
            except Exception as exc:
                duration_ms = int((time.monotonic() - case_start) * 1000)
                cases.append(CertificationCaseResult(
                    scenario=scenario, status=CaseStatus.ERROR, trace_id=None,
                    failures=(f"{type(exc).__name__}: certification case execution failed",),
                    duration_ms=duration_ms, event_count=0,
                ))
        completed = max(
            datetime.now(timezone.utc).replace(microsecond=0), start
        )
        status = (
            CertificationStatus.PASSED
            if all(case.status is CaseStatus.PASSED for case in cases)
            else CertificationStatus.FAILED
        )
        report_id = CertificationReport.content_id(
            run_id=run_id, suite_id=selected.suite_id,
            suite_version=selected.suite_version,
            adapter_binding_ref=driver.adapter_binding_ref,
            manifest_payload_sha256=manifest_payload_sha256,
            evidence_classification=driver.evidence_classification,
            status=status, cases=tuple(cases),
            started_at=start, completed_at=completed,
        )
        report = CertificationReport(
            report_id, run_id, selected.suite_id, selected.suite_version,
            driver.adapter_binding_ref, manifest_payload_sha256,
            driver.evidence_classification, status, tuple(cases), start, completed,
        )
        if recorder is not None:
            recorder.complete(report)
        return report
