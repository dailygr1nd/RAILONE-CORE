"""Canonical certification traces and immutable report models."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Mapping

from railone_crypto.canonical_json import canonical_json_bytes
from railone_crypto.signature_service import SignatureEnvelope


class CertificationScenario(StrEnum):
    P2P_SETTLED = "P2P_SETTLED"
    MERCHANT_SUPPLIER_SETTLED = "MERCHANT_SUPPLIER_SETTLED"
    CROSS_BORDER_SETTLED = "CROSS_BORDER_SETTLED"
    DUPLICATE_SUBMISSION = "DUPLICATE_SUBMISSION"
    UNKNOWN_THEN_RECONCILED = "UNKNOWN_THEN_RECONCILED"
    TAMPERED_CALLBACK_REJECTED = "TAMPERED_CALLBACK_REJECTED"
    DUPLICATE_CALLBACK_EXACTLY_ONCE = "DUPLICATE_CALLBACK_EXACTLY_ONCE"
    SETTLEMENT_AMOUNT_MISMATCH_REJECTED = "SETTLEMENT_AMOUNT_MISMATCH_REJECTED"
    HISTORY_ACCESS_CONTROL = "HISTORY_ACCESS_CONTROL"
    SMS_FINALITY_GATE = "SMS_FINALITY_GATE"
    ADAPTER_VERSION_PIN = "ADAPTER_VERSION_PIN"


class TraceEventType(StrEnum):
    INTENT_ACCEPTED = "INTENT_ACCEPTED"
    UTT_CREATED = "UTT_CREATED"
    FX_QUOTE_BOUND = "FX_QUOTE_BOUND"
    HISTORY_INDEXED = "HISTORY_INDEXED"
    PLAN_CREATED = "PLAN_CREATED"
    RTT_CREATED = "RTT_CREATED"
    ADAPTER_BINDING_VERIFIED = "ADAPTER_BINDING_VERIFIED"
    ADAPTER_BINDING_MISMATCH_REJECTED = "ADAPTER_BINDING_MISMATCH_REJECTED"
    PROVIDER_DISPATCHED = "PROVIDER_DISPATCHED"
    PROVIDER_ACCEPTED = "PROVIDER_ACCEPTED"
    IDEMPOTENT_REPLAY_RETURNED = "IDEMPOTENT_REPLAY_RETURNED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    CALLBACK_ACCEPTED = "CALLBACK_ACCEPTED"
    CALLBACK_REJECTED = "CALLBACK_REJECTED"
    EXTERNAL_EVIDENCE_VERIFIED = "EXTERNAL_EVIDENCE_VERIFIED"
    EXTERNAL_EVIDENCE_REJECTED = "EXTERNAL_EVIDENCE_REJECTED"
    RTT_SUCCEEDED = "RTT_SUCCEEDED"
    RTT_FAILED = "RTT_FAILED"
    PLAN_FINALIZED = "PLAN_FINALIZED"
    SMS_BLOCKED_BEFORE_FINALITY = "SMS_BLOCKED_BEFORE_FINALITY"
    SMS_PREPARED = "SMS_PREPARED"
    SMS_SENT = "SMS_SENT"
    HISTORY_READ_ALLOWED = "HISTORY_READ_ALLOWED"
    HISTORY_READ_DENIED = "HISTORY_READ_DENIED"


class CaseStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    ERROR = "ERROR"


class CertificationStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"


class EvidenceClassification(StrEnum):
    SYNTHETIC_SELF_TEST = "SYNTHETIC_SELF_TEST"
    PARTNER_SANDBOX = "PARTNER_SANDBOX"


_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_BINDING_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,127}@[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")
_SAFE_METADATA_KEYS = frozenset({
    "actor_scope", "channel", "corridor", "currency_from", "currency_to",
    "finality", "outcome", "provider_code", "recipient_role", "replayed",
    "route_id", "transport", "verification",
})


def _instant(name: str, value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _event_material(
    *,
    scenario: CertificationScenario,
    event_type: TraceEventType,
    occurred_at: datetime,
    sequence: int,
    utt_id: str | None,
    rtt_id: str | None,
    adapter_binding_ref: str,
    evidence_sha256: str | None,
    metadata: tuple[tuple[str, str], ...],
) -> dict[str, object]:
    return {
        "scenario": scenario.value,
        "event_type": event_type.value,
        "occurred_at": int(occurred_at.timestamp()),
        "sequence": sequence,
        "utt_id": utt_id,
        "rtt_id": rtt_id,
        "adapter_binding_ref": adapter_binding_ref,
        "evidence_sha256": evidence_sha256,
        "metadata": {key: value for key, value in metadata},
    }


@dataclass(frozen=True, slots=True)
class CertificationTraceEvent:
    event_id: str
    scenario: CertificationScenario
    event_type: TraceEventType
    occurred_at: datetime
    sequence: int
    adapter_binding_ref: str
    utt_id: str | None = None
    rtt_id: str | None = None
    evidence_sha256: str | None = None
    metadata: tuple[tuple[str, str], ...] = field(default=(), repr=False)

    def __post_init__(self) -> None:
        instant = _instant("occurred_at", self.occurred_at)
        object.__setattr__(self, "occurred_at", instant)
        if self.sequence < 1:
            raise ValueError("certification event sequence must be positive")
        if not _BINDING_REF.fullmatch(self.adapter_binding_ref):
            raise ValueError("certification event requires adapter_id@semantic-version")
        if self.evidence_sha256 is not None and not _SHA256.fullmatch(self.evidence_sha256):
            raise ValueError("evidence_sha256 must be a lowercase SHA-256 digest")
        normalized = tuple(sorted((str(key), str(value)) for key, value in self.metadata))
        if len(normalized) != len({key for key, _ in normalized}):
            raise ValueError("certification event metadata keys must be unique")
        if any(key not in _SAFE_METADATA_KEYS for key, _ in normalized):
            raise ValueError("certification event metadata contains a non-canonical key")
        if any(not value or len(value) > 128 for _, value in normalized):
            raise ValueError("certification event metadata values must be non-empty and bounded")
        object.__setattr__(self, "metadata", normalized)
        expected = self.content_id(
            scenario=self.scenario,
            event_type=self.event_type,
            occurred_at=instant,
            sequence=self.sequence,
            adapter_binding_ref=self.adapter_binding_ref,
            utt_id=self.utt_id,
            rtt_id=self.rtt_id,
            evidence_sha256=self.evidence_sha256,
            metadata=normalized,
        )
        if self.event_id != expected:
            raise ValueError("certification event content identifier mismatch")

    @classmethod
    def create(
        cls,
        *,
        scenario: CertificationScenario,
        event_type: TraceEventType,
        occurred_at: datetime,
        sequence: int,
        adapter_binding_ref: str,
        utt_id: str | None = None,
        rtt_id: str | None = None,
        evidence_sha256: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> "CertificationTraceEvent":
        normalized = tuple(sorted((metadata or {}).items()))
        event_id = cls.content_id(
            scenario=scenario, event_type=event_type, occurred_at=occurred_at,
            sequence=sequence, adapter_binding_ref=adapter_binding_ref,
            utt_id=utt_id, rtt_id=rtt_id, evidence_sha256=evidence_sha256,
            metadata=normalized,
        )
        return cls(
            event_id, scenario, event_type, occurred_at, sequence,
            adapter_binding_ref, utt_id, rtt_id, evidence_sha256, normalized,
        )

    @staticmethod
    def content_id(**values) -> str:
        digest = hashlib.sha256(canonical_json_bytes(_event_material(**values))).hexdigest()
        return f"CERT-EVT-{digest[:32].upper()}"

    def to_payload(self) -> dict[str, object]:
        return {"event_id": self.event_id, **_event_material(
            scenario=self.scenario, event_type=self.event_type,
            occurred_at=self.occurred_at, sequence=self.sequence,
            utt_id=self.utt_id, rtt_id=self.rtt_id,
            adapter_binding_ref=self.adapter_binding_ref,
            evidence_sha256=self.evidence_sha256, metadata=self.metadata,
        )}


@dataclass(frozen=True, slots=True)
class CertificationTrace:
    trace_id: str
    run_id: str
    scenario: CertificationScenario
    adapter_binding_ref: str
    started_at: datetime
    completed_at: datetime
    events: tuple[CertificationTraceEvent, ...]

    def __post_init__(self) -> None:
        start = _instant("started_at", self.started_at)
        end = _instant("completed_at", self.completed_at)
        object.__setattr__(self, "started_at", start)
        object.__setattr__(self, "completed_at", end)
        if end < start:
            raise ValueError("certification trace cannot complete before it starts")
        if not self.events:
            raise ValueError("certification trace cannot be empty")
        if tuple(event.sequence for event in self.events) != tuple(range(1, len(self.events) + 1)):
            raise ValueError("certification event sequence must be contiguous and ordered")
        if any(event.scenario is not self.scenario for event in self.events):
            raise ValueError("certification trace contains another scenario")
        if any(event.adapter_binding_ref != self.adapter_binding_ref for event in self.events):
            raise ValueError("certification trace changed adapter binding")
        expected = self.content_id(
            run_id=self.run_id, scenario=self.scenario,
            adapter_binding_ref=self.adapter_binding_ref,
            started_at=start, completed_at=end, events=self.events,
        )
        if self.trace_id != expected:
            raise ValueError("certification trace content identifier mismatch")

    @classmethod
    def create(cls, *, run_id: str, scenario: CertificationScenario,
               adapter_binding_ref: str, started_at: datetime,
               completed_at: datetime, events: tuple[CertificationTraceEvent, ...]):
        trace_id = cls.content_id(
            run_id=run_id, scenario=scenario, adapter_binding_ref=adapter_binding_ref,
            started_at=started_at, completed_at=completed_at, events=events,
        )
        return cls(trace_id, run_id, scenario, adapter_binding_ref,
                   started_at, completed_at, events)

    @staticmethod
    def content_id(*, run_id, scenario, adapter_binding_ref, started_at, completed_at, events):
        material = {
            "run_id": run_id, "scenario": scenario.value,
            "adapter_binding_ref": adapter_binding_ref,
            "started_at": int(started_at.timestamp()),
            "completed_at": int(completed_at.timestamp()),
            "events": [event.to_payload() for event in events],
        }
        return "CERT-TRACE-" + hashlib.sha256(canonical_json_bytes(material)).hexdigest()[:32].upper()

    def to_payload(self) -> dict[str, object]:
        return {
            "trace_id": self.trace_id, "run_id": self.run_id,
            "scenario": self.scenario.value,
            "adapter_binding_ref": self.adapter_binding_ref,
            "started_at": int(self.started_at.timestamp()),
            "completed_at": int(self.completed_at.timestamp()),
            "events": [event.to_payload() for event in self.events],
        }


@dataclass(frozen=True, slots=True)
class CertificationCaseResult:
    scenario: CertificationScenario
    status: CaseStatus
    trace_id: str | None
    failures: tuple[str, ...]
    duration_ms: int
    event_count: int

    def __post_init__(self) -> None:
        if self.duration_ms < 0 or self.event_count < 0:
            raise ValueError("certification case metrics cannot be negative")
        if self.status is CaseStatus.PASSED and self.failures:
            raise ValueError("passed certification case cannot contain failures")
        if self.status is not CaseStatus.PASSED and not self.failures:
            raise ValueError("failed certification case requires a reason")

    def to_payload(self) -> dict[str, object]:
        return {
            "scenario": self.scenario.value, "status": self.status.value,
            "trace_id": self.trace_id, "failures": list(self.failures),
            "duration_ms": self.duration_ms, "event_count": self.event_count,
        }


@dataclass(frozen=True, slots=True)
class CertificationReport:
    report_id: str
    run_id: str
    suite_id: str
    suite_version: str
    adapter_binding_ref: str
    manifest_payload_sha256: str
    evidence_classification: EvidenceClassification
    status: CertificationStatus
    cases: tuple[CertificationCaseResult, ...]
    started_at: datetime
    completed_at: datetime

    def __post_init__(self) -> None:
        start = _instant("started_at", self.started_at)
        end = _instant("completed_at", self.completed_at)
        object.__setattr__(self, "started_at", start)
        object.__setattr__(self, "completed_at", end)
        if end < start:
            raise ValueError("certification report cannot complete before it starts")
        if not _BINDING_REF.fullmatch(self.adapter_binding_ref):
            raise ValueError("certification report requires adapter_id@semantic-version")
        if not _SHA256.fullmatch(self.manifest_payload_sha256):
            raise ValueError("manifest_payload_sha256 must be a lowercase SHA-256 digest")
        if not self.cases or len({case.scenario for case in self.cases}) != len(self.cases):
            raise ValueError("certification report requires unique case results")
        expected_status = (
            CertificationStatus.PASSED
            if all(case.status is CaseStatus.PASSED for case in self.cases)
            else CertificationStatus.FAILED
        )
        if self.status is not expected_status:
            raise ValueError("certification report status disagrees with case results")
        if self.report_id != self.content_id(
            run_id=self.run_id, suite_id=self.suite_id,
            suite_version=self.suite_version,
            adapter_binding_ref=self.adapter_binding_ref,
            manifest_payload_sha256=self.manifest_payload_sha256,
            evidence_classification=self.evidence_classification,
            status=self.status, cases=self.cases,
            started_at=start, completed_at=end,
        ):
            raise ValueError("certification report content identifier mismatch")

    @staticmethod
    def content_id(*, run_id, suite_id, suite_version, adapter_binding_ref,
                   manifest_payload_sha256, evidence_classification, status,
                   cases, started_at, completed_at):
        core = {
            "run_id": run_id, "suite_id": suite_id,
            "suite_version": suite_version,
            "adapter_binding_ref": adapter_binding_ref,
            "manifest_payload_sha256": manifest_payload_sha256,
            "evidence_classification": evidence_classification.value,
            "status": status.value,
            "cases": [case.to_payload() for case in cases],
            "started_at": int(started_at.timestamp()),
            "completed_at": int(completed_at.timestamp()),
        }
        return "CERT-REPORT-" + hashlib.sha256(canonical_json_bytes(core)).hexdigest()[:32].upper()

    def to_payload(self) -> dict[str, object]:
        return {
            "report_id": self.report_id, "run_id": self.run_id,
            "suite_id": self.suite_id, "suite_version": self.suite_version,
            "adapter_binding_ref": self.adapter_binding_ref,
            "manifest_payload_sha256": self.manifest_payload_sha256,
            "evidence_classification": self.evidence_classification.value,
            "status": self.status.value,
            "cases": [case.to_payload() for case in self.cases],
            "started_at": int(self.started_at.timestamp()),
            "completed_at": int(self.completed_at.timestamp()),
        }


@dataclass(frozen=True, slots=True)
class SignedCertificationReport:
    report: CertificationReport
    signature: SignatureEnvelope
