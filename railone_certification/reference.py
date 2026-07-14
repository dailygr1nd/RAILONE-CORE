"""Synthetic trace driver used to prove the harness itself, never a partner."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from .models import (
    CertificationScenario, CertificationTrace, CertificationTraceEvent,
    EvidenceClassification, TraceEventType,
)


class SyntheticReferenceCertificationDriver:
    """Produces deterministic conforming traces for harness self-tests.

    A report generated from this driver is synthetic evidence and cannot be used
    to certify a real institution, scheme, corridor or adapter deployment.
    """

    def __init__(self, adapter_binding_ref: str) -> None:
        self.adapter_binding_ref = adapter_binding_ref
        self.evidence_classification = EvidenceClassification.SYNTHETIC_SELF_TEST

    def execute_case(
        self, *, run_id: str, scenario: CertificationScenario
    ) -> CertificationTrace:
        started = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)
        utt_id = f"UTT-CERT-{scenario.value}"
        rtt_id = f"RTT-CERT-{scenario.value}"
        rows: list[tuple[TraceEventType, dict[str, str], bool]] = []

        def add(kind: TraceEventType, metadata=None, evidence=False):
            rows.append((kind, metadata or {}, evidence))

        if scenario in {
            CertificationScenario.P2P_SETTLED,
            CertificationScenario.MERCHANT_SUPPLIER_SETTLED,
            CertificationScenario.CROSS_BORDER_SETTLED,
        }:
            add(TraceEventType.INTENT_ACCEPTED)
            add(TraceEventType.UTT_CREATED)
            if scenario is CertificationScenario.CROSS_BORDER_SETTLED:
                add(TraceEventType.FX_QUOTE_BOUND, {"currency_from": "USD", "currency_to": "KES", "corridor": "US-KE"})
            add(TraceEventType.HISTORY_INDEXED)
            add(TraceEventType.PLAN_CREATED)
            add(TraceEventType.RTT_CREATED)
            add(TraceEventType.ADAPTER_BINDING_VERIFIED, {"verification": "EXACT_VERSION"})
            add(TraceEventType.PROVIDER_DISPATCHED)
            add(TraceEventType.PROVIDER_ACCEPTED, {"finality": "PROCESSING"})
            add(TraceEventType.EXTERNAL_EVIDENCE_VERIFIED, {"finality": "SETTLED"}, True)
            add(TraceEventType.RTT_SUCCEEDED)
            add(TraceEventType.PLAN_FINALIZED)
            add(TraceEventType.SMS_PREPARED, {"recipient_role": "SENDER", "channel": "SMS"})
            add(TraceEventType.SMS_PREPARED, {"recipient_role": "RECEIVER", "channel": "SMS"})
            scopes = (
                ("MERCHANT", "BRANCH")
                if scenario is CertificationScenario.MERCHANT_SUPPLIER_SETTLED
                else ("SENDER", "RECEIVER")
            )
            for scope in scopes:
                add(TraceEventType.HISTORY_READ_ALLOWED, {"actor_scope": scope})
        elif scenario is CertificationScenario.DUPLICATE_SUBMISSION:
            add(TraceEventType.UTT_CREATED)
            add(TraceEventType.RTT_CREATED)
            add(TraceEventType.PROVIDER_DISPATCHED)
            add(TraceEventType.PROVIDER_ACCEPTED, {"finality": "PROCESSING"})
            add(TraceEventType.IDEMPOTENT_REPLAY_RETURNED, {"replayed": "true"})
        elif scenario is CertificationScenario.UNKNOWN_THEN_RECONCILED:
            add(TraceEventType.UTT_CREATED)
            add(TraceEventType.RTT_CREATED)
            add(TraceEventType.PROVIDER_DISPATCHED)
            add(TraceEventType.OUTCOME_UNKNOWN, {"outcome": "UNKNOWN"})
            add(TraceEventType.RECONCILIATION_REQUIRED)
            add(TraceEventType.EXTERNAL_EVIDENCE_VERIFIED, {"finality": "SETTLED"}, True)
            add(TraceEventType.RTT_SUCCEEDED)
            add(TraceEventType.PLAN_FINALIZED)
        elif scenario is CertificationScenario.TAMPERED_CALLBACK_REJECTED:
            add(TraceEventType.UTT_CREATED)
            add(TraceEventType.RTT_CREATED)
            add(TraceEventType.CALLBACK_REJECTED, {"verification": "INVALID_SIGNATURE"}, True)
        elif scenario is CertificationScenario.DUPLICATE_CALLBACK_EXACTLY_ONCE:
            add(TraceEventType.UTT_CREATED)
            add(TraceEventType.RTT_CREATED)
            add(TraceEventType.CALLBACK_ACCEPTED, {"replayed": "false"}, True)
            add(TraceEventType.EXTERNAL_EVIDENCE_VERIFIED, {"finality": "SETTLED"}, True)
            add(TraceEventType.RTT_SUCCEEDED)
            add(TraceEventType.PLAN_FINALIZED)
            add(TraceEventType.SMS_PREPARED, {"recipient_role": "SENDER"})
            add(TraceEventType.SMS_PREPARED, {"recipient_role": "RECEIVER"})
            add(TraceEventType.CALLBACK_ACCEPTED, {"replayed": "true"}, True)
        elif scenario is CertificationScenario.SETTLEMENT_AMOUNT_MISMATCH_REJECTED:
            add(TraceEventType.UTT_CREATED)
            add(TraceEventType.RTT_CREATED)
            add(TraceEventType.CALLBACK_ACCEPTED, {}, True)
            add(TraceEventType.EXTERNAL_EVIDENCE_REJECTED, {"verification": "AMOUNT_MISMATCH"}, True)
        elif scenario is CertificationScenario.HISTORY_ACCESS_CONTROL:
            add(TraceEventType.UTT_CREATED)
            add(TraceEventType.HISTORY_INDEXED)
            add(TraceEventType.HISTORY_READ_ALLOWED, {"actor_scope": "SENDER"})
            add(TraceEventType.HISTORY_READ_ALLOWED, {"actor_scope": "RECEIVER"})
            add(TraceEventType.HISTORY_READ_DENIED, {"actor_scope": "UNRELATED"})
        elif scenario is CertificationScenario.SMS_FINALITY_GATE:
            add(TraceEventType.UTT_CREATED)
            add(TraceEventType.RTT_CREATED)
            add(TraceEventType.SMS_BLOCKED_BEFORE_FINALITY)
            add(TraceEventType.EXTERNAL_EVIDENCE_VERIFIED, {"finality": "SETTLED"}, True)
            add(TraceEventType.RTT_SUCCEEDED)
            add(TraceEventType.PLAN_FINALIZED)
            add(TraceEventType.SMS_PREPARED, {"recipient_role": "SENDER"})
            add(TraceEventType.SMS_PREPARED, {"recipient_role": "RECEIVER"})
        elif scenario is CertificationScenario.ADAPTER_VERSION_PIN:
            add(TraceEventType.UTT_CREATED)
            add(TraceEventType.RTT_CREATED)
            add(TraceEventType.ADAPTER_BINDING_VERIFIED, {"verification": "EXACT_VERSION"})
            add(TraceEventType.PROVIDER_DISPATCHED)
            add(TraceEventType.ADAPTER_BINDING_MISMATCH_REJECTED, {"verification": "VERSION_MISMATCH"})
        else:  # pragma: no cover - enum exhaustiveness guard
            raise ValueError(f"unsupported synthetic certification scenario: {scenario}")

        events = tuple(
            CertificationTraceEvent.create(
                scenario=scenario, event_type=kind,
                occurred_at=started + timedelta(seconds=index), sequence=index,
                adapter_binding_ref=self.adapter_binding_ref,
                utt_id=utt_id,
                rtt_id=rtt_id if kind not in {TraceEventType.INTENT_ACCEPTED, TraceEventType.UTT_CREATED, TraceEventType.HISTORY_INDEXED} else None,
                evidence_sha256=(
                    hashlib.sha256(f"{run_id}:{scenario.value}:{index}".encode()).hexdigest()
                    if evidence else None
                ),
                metadata=metadata,
            )
            for index, (kind, metadata, evidence) in enumerate(rows, start=1)
        )
        return CertificationTrace.create(
            run_id=run_id, scenario=scenario,
            adapter_binding_ref=self.adapter_binding_ref,
            started_at=started, completed_at=events[-1].occurred_at,
            events=events,
        )
