"""Strict JSON codecs for certification traces and reports."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Mapping

from .models import (
    CaseStatus, CertificationCaseResult, CertificationReport,
    CertificationScenario, CertificationStatus, CertificationTrace,
    CertificationTraceEvent, TraceEventType,
    EvidenceClassification,
)


def trace_from_payload(value: Mapping[str, object]) -> CertificationTrace:
    raw_events = value.get("events")
    if not isinstance(raw_events, list):
        raise ValueError("certification trace events must be an array")
    events = tuple(_event(item) for item in raw_events)
    return CertificationTrace(
        trace_id=_text(value, "trace_id"),
        run_id=_text(value, "run_id"),
        scenario=CertificationScenario(_text(value, "scenario")),
        adapter_binding_ref=_text(value, "adapter_binding_ref"),
        started_at=_epoch(value, "started_at"),
        completed_at=_epoch(value, "completed_at"),
        events=events,
    )


def report_from_payload(value: Mapping[str, object]) -> CertificationReport:
    raw_cases = value.get("cases")
    if not isinstance(raw_cases, list):
        raise ValueError("certification report cases must be an array")
    cases = tuple(_case(item) for item in raw_cases)
    return CertificationReport(
        report_id=_text(value, "report_id"),
        run_id=_text(value, "run_id"),
        suite_id=_text(value, "suite_id"),
        suite_version=_text(value, "suite_version"),
        adapter_binding_ref=_text(value, "adapter_binding_ref"),
        manifest_payload_sha256=_text(value, "manifest_payload_sha256"),
        evidence_classification=EvidenceClassification(
            _text(value, "evidence_classification")
        ),
        status=CertificationStatus(_text(value, "status")),
        cases=cases,
        started_at=_epoch(value, "started_at"),
        completed_at=_epoch(value, "completed_at"),
    )


def load_trace_json(body: bytes, *, max_bytes: int = 5_000_000) -> CertificationTrace:
    if len(body) > max_bytes:
        raise ValueError("certification trace exceeds the input size limit")
    value = json.loads(body.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("certification trace must be a JSON object")
    return trace_from_payload(value)


def _event(value: object) -> CertificationTraceEvent:
    if not isinstance(value, Mapping):
        raise ValueError("certification event must be an object")
    metadata = value.get("metadata", {})
    if not isinstance(metadata, Mapping):
        raise ValueError("certification event metadata must be an object")
    evidence = value.get("evidence_sha256")
    if evidence is not None and not isinstance(evidence, str):
        raise ValueError("certification event evidence hash must be text")
    return CertificationTraceEvent(
        event_id=_text(value, "event_id"),
        scenario=CertificationScenario(_text(value, "scenario")),
        event_type=TraceEventType(_text(value, "event_type")),
        occurred_at=_epoch(value, "occurred_at"),
        sequence=_integer(value, "sequence"),
        adapter_binding_ref=_text(value, "adapter_binding_ref"),
        utt_id=_optional_text(value, "utt_id"),
        rtt_id=_optional_text(value, "rtt_id"),
        evidence_sha256=evidence,
        metadata=tuple((str(key), str(item)) for key, item in metadata.items()),
    )


def _case(value: object) -> CertificationCaseResult:
    if not isinstance(value, Mapping):
        raise ValueError("certification case must be an object")
    failures = value.get("failures")
    if not isinstance(failures, list) or any(not isinstance(item, str) for item in failures):
        raise ValueError("certification failures must be an array of strings")
    return CertificationCaseResult(
        scenario=CertificationScenario(_text(value, "scenario")),
        status=CaseStatus(_text(value, "status")),
        trace_id=_optional_text(value, "trace_id"),
        failures=tuple(failures),
        duration_ms=_integer(value, "duration_ms"),
        event_count=_integer(value, "event_count"),
    )


def _text(value: Mapping[str, object], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise ValueError(f"{key} must be non-empty text")
    return item


def _optional_text(value: Mapping[str, object], key: str) -> str | None:
    item = value.get(key)
    if item is None:
        return None
    if not isinstance(item, str) or not item:
        raise ValueError(f"{key} must be non-empty text when present")
    return item


def _integer(value: Mapping[str, object], key: str) -> int:
    item = value.get(key)
    if isinstance(item, bool) or not isinstance(item, int):
        raise ValueError(f"{key} must be an integer")
    return item


def _epoch(value: Mapping[str, object], key: str) -> datetime:
    return datetime.fromtimestamp(_integer(value, key), tz=timezone.utc)
