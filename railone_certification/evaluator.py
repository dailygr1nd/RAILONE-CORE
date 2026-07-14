"""Fail-closed evaluation of canonical partner certification traces."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .models import CertificationScenario, CertificationTrace, TraceEventType


@dataclass(frozen=True, slots=True)
class _Expectation:
    exact: tuple[tuple[TraceEventType, int], ...] = ()
    minimum: tuple[tuple[TraceEventType, int], ...] = ()
    forbidden: tuple[TraceEventType, ...] = ()
    ordered: tuple[tuple[TraceEventType, TraceEventType], ...] = ()
    required_scopes: tuple[str, ...] = ()


_HAPPY_ORDER = (
    (TraceEventType.UTT_CREATED, TraceEventType.RTT_CREATED),
    (TraceEventType.RTT_CREATED, TraceEventType.PROVIDER_DISPATCHED),
    (TraceEventType.PROVIDER_DISPATCHED, TraceEventType.PROVIDER_ACCEPTED),
    (TraceEventType.PROVIDER_ACCEPTED, TraceEventType.EXTERNAL_EVIDENCE_VERIFIED),
    (TraceEventType.EXTERNAL_EVIDENCE_VERIFIED, TraceEventType.RTT_SUCCEEDED),
    (TraceEventType.RTT_SUCCEEDED, TraceEventType.PLAN_FINALIZED),
    (TraceEventType.PLAN_FINALIZED, TraceEventType.SMS_PREPARED),
)
_HAPPY_EXACT = (
    (TraceEventType.UTT_CREATED, 1),
    (TraceEventType.RTT_CREATED, 1),
    (TraceEventType.ADAPTER_BINDING_VERIFIED, 1),
    (TraceEventType.PROVIDER_DISPATCHED, 1),
    (TraceEventType.PROVIDER_ACCEPTED, 1),
    (TraceEventType.EXTERNAL_EVIDENCE_VERIFIED, 1),
    (TraceEventType.RTT_SUCCEEDED, 1),
    (TraceEventType.PLAN_FINALIZED, 1),
    (TraceEventType.SMS_PREPARED, 2),
)


_EXPECTATIONS = {
    CertificationScenario.P2P_SETTLED: _Expectation(
        exact=_HAPPY_EXACT,
        minimum=((TraceEventType.HISTORY_READ_ALLOWED, 2),),
        ordered=_HAPPY_ORDER,
        required_scopes=("SENDER", "RECEIVER"),
    ),
    CertificationScenario.MERCHANT_SUPPLIER_SETTLED: _Expectation(
        exact=_HAPPY_EXACT,
        minimum=((TraceEventType.HISTORY_READ_ALLOWED, 2),),
        ordered=_HAPPY_ORDER,
        required_scopes=("MERCHANT", "BRANCH"),
    ),
    CertificationScenario.CROSS_BORDER_SETTLED: _Expectation(
        exact=_HAPPY_EXACT + ((TraceEventType.FX_QUOTE_BOUND, 1),),
        minimum=((TraceEventType.HISTORY_READ_ALLOWED, 2),),
        ordered=_HAPPY_ORDER + ((TraceEventType.UTT_CREATED, TraceEventType.FX_QUOTE_BOUND),),
        required_scopes=("SENDER", "RECEIVER"),
    ),
    CertificationScenario.DUPLICATE_SUBMISSION: _Expectation(
        exact=(
            (TraceEventType.UTT_CREATED, 1),
            (TraceEventType.RTT_CREATED, 1),
            (TraceEventType.PROVIDER_DISPATCHED, 1),
            (TraceEventType.PROVIDER_ACCEPTED, 1),
            (TraceEventType.IDEMPOTENT_REPLAY_RETURNED, 1),
        ),
        ordered=((TraceEventType.PROVIDER_DISPATCHED, TraceEventType.IDEMPOTENT_REPLAY_RETURNED),),
    ),
    CertificationScenario.UNKNOWN_THEN_RECONCILED: _Expectation(
        exact=(
            (TraceEventType.UTT_CREATED, 1),
            (TraceEventType.RTT_CREATED, 1),
            (TraceEventType.PROVIDER_DISPATCHED, 1),
            (TraceEventType.OUTCOME_UNKNOWN, 1),
            (TraceEventType.RECONCILIATION_REQUIRED, 1),
            (TraceEventType.EXTERNAL_EVIDENCE_VERIFIED, 1),
            (TraceEventType.RTT_SUCCEEDED, 1),
            (TraceEventType.PLAN_FINALIZED, 1),
        ),
        ordered=(
            (TraceEventType.PROVIDER_DISPATCHED, TraceEventType.OUTCOME_UNKNOWN),
            (TraceEventType.OUTCOME_UNKNOWN, TraceEventType.RECONCILIATION_REQUIRED),
            (TraceEventType.RECONCILIATION_REQUIRED, TraceEventType.EXTERNAL_EVIDENCE_VERIFIED),
            (TraceEventType.EXTERNAL_EVIDENCE_VERIFIED, TraceEventType.RTT_SUCCEEDED),
        ),
    ),
    CertificationScenario.TAMPERED_CALLBACK_REJECTED: _Expectation(
        exact=((TraceEventType.CALLBACK_REJECTED, 1),),
        forbidden=(
            TraceEventType.EXTERNAL_EVIDENCE_VERIFIED, TraceEventType.RTT_SUCCEEDED,
            TraceEventType.PLAN_FINALIZED, TraceEventType.SMS_PREPARED,
        ),
    ),
    CertificationScenario.DUPLICATE_CALLBACK_EXACTLY_ONCE: _Expectation(
        exact=(
            (TraceEventType.CALLBACK_ACCEPTED, 2),
            (TraceEventType.EXTERNAL_EVIDENCE_VERIFIED, 1),
            (TraceEventType.RTT_SUCCEEDED, 1),
            (TraceEventType.PLAN_FINALIZED, 1),
            (TraceEventType.SMS_PREPARED, 2),
        ),
        ordered=((TraceEventType.CALLBACK_ACCEPTED, TraceEventType.EXTERNAL_EVIDENCE_VERIFIED),),
    ),
    CertificationScenario.SETTLEMENT_AMOUNT_MISMATCH_REJECTED: _Expectation(
        exact=((TraceEventType.EXTERNAL_EVIDENCE_REJECTED, 1),),
        forbidden=(TraceEventType.RTT_SUCCEEDED, TraceEventType.PLAN_FINALIZED, TraceEventType.SMS_PREPARED),
    ),
    CertificationScenario.HISTORY_ACCESS_CONTROL: _Expectation(
        minimum=((TraceEventType.HISTORY_READ_ALLOWED, 2),),
        exact=((TraceEventType.HISTORY_READ_DENIED, 1),),
        required_scopes=("SENDER", "RECEIVER", "UNRELATED"),
    ),
    CertificationScenario.SMS_FINALITY_GATE: _Expectation(
        exact=(
            (TraceEventType.SMS_BLOCKED_BEFORE_FINALITY, 1),
            (TraceEventType.EXTERNAL_EVIDENCE_VERIFIED, 1),
            (TraceEventType.RTT_SUCCEEDED, 1),
            (TraceEventType.PLAN_FINALIZED, 1),
            (TraceEventType.SMS_PREPARED, 2),
        ),
        ordered=(
            (TraceEventType.SMS_BLOCKED_BEFORE_FINALITY, TraceEventType.EXTERNAL_EVIDENCE_VERIFIED),
            (TraceEventType.PLAN_FINALIZED, TraceEventType.SMS_PREPARED),
        ),
    ),
    CertificationScenario.ADAPTER_VERSION_PIN: _Expectation(
        exact=(
            (TraceEventType.UTT_CREATED, 1),
            (TraceEventType.RTT_CREATED, 1),
            (TraceEventType.ADAPTER_BINDING_VERIFIED, 1),
            (TraceEventType.ADAPTER_BINDING_MISMATCH_REJECTED, 1),
            (TraceEventType.PROVIDER_DISPATCHED, 1),
        ),
        ordered=(
            (TraceEventType.RTT_CREATED, TraceEventType.ADAPTER_BINDING_VERIFIED),
            (TraceEventType.ADAPTER_BINDING_VERIFIED, TraceEventType.PROVIDER_DISPATCHED),
        ),
    ),
}


class CertificationTraceEvaluator:
    def evaluate(self, trace: CertificationTrace) -> tuple[str, ...]:
        failures: list[str] = []
        expected = _EXPECTATIONS[trace.scenario]
        counts = Counter(event.event_type for event in trace.events)
        for event_type, count in expected.exact:
            if counts[event_type] != count:
                failures.append(f"{event_type.value}: expected exactly {count}, observed {counts[event_type]}")
        for event_type, count in expected.minimum:
            if counts[event_type] < count:
                failures.append(f"{event_type.value}: expected at least {count}, observed {counts[event_type]}")
        for event_type in expected.forbidden:
            if counts[event_type]:
                failures.append(f"{event_type.value}: forbidden event observed")
        for before, after in expected.ordered:
            if counts[before] and counts[after] and self._first(trace, before) >= self._first(trace, after):
                failures.append(f"event order violated: {before.value} must precede {after.value}")
        scopes = {
            dict(event.metadata).get("actor_scope")
            for event in trace.events
            if event.event_type in {TraceEventType.HISTORY_READ_ALLOWED, TraceEventType.HISTORY_READ_DENIED}
        }
        for scope in expected.required_scopes:
            if scope not in scopes:
                failures.append(f"history scope was not exercised: {scope}")
        failures.extend(self._global_invariants(trace, counts))
        return tuple(sorted(set(failures)))

    @staticmethod
    def _first(trace: CertificationTrace, kind: TraceEventType) -> int:
        return next(event.sequence for event in trace.events if event.event_type is kind)

    def _global_invariants(self, trace, counts) -> list[str]:
        failures: list[str] = []
        timestamps = [event.occurred_at for event in trace.events]
        if timestamps != sorted(timestamps):
            failures.append("event timestamps are not monotonic")
        utt_ids = {event.utt_id for event in trace.events if event.utt_id is not None}
        if len(utt_ids) > 1:
            failures.append("one certification case emitted multiple UTT identities")
        if counts[TraceEventType.RTT_CREATED] and not counts[TraceEventType.UTT_CREATED]:
            failures.append("RTT exists without a preceding UTT")
        if counts[TraceEventType.RTT_SUCCEEDED] and not counts[TraceEventType.EXTERNAL_EVIDENCE_VERIFIED]:
            failures.append("RTT succeeded without verified external evidence")
        if any(
            event.event_type is TraceEventType.EXTERNAL_EVIDENCE_VERIFIED
            and event.evidence_sha256 is None
            for event in trace.events
        ):
            failures.append("verified external evidence omitted its evidence hash")
        if counts[TraceEventType.PLAN_FINALIZED] and not counts[TraceEventType.RTT_SUCCEEDED]:
            failures.append("plan finalized without a successful RTT")
        if counts[TraceEventType.SMS_PREPARED] and not counts[TraceEventType.PLAN_FINALIZED]:
            failures.append("settlement SMS was prepared before plan finality")
        if counts[TraceEventType.OUTCOME_UNKNOWN] and counts[TraceEventType.PROVIDER_DISPATCHED] > 1:
            failures.append("unknown provider outcome caused a blind redispatch")
        rtt_ids = {event.rtt_id for event in trace.events if event.rtt_id is not None}
        if len(rtt_ids) > 1 and trace.scenario is not CertificationScenario.UNKNOWN_THEN_RECONCILED:
            failures.append("case changed RTT identity without an explicit retry scenario")
        if len({event.event_id for event in trace.events}) != len(trace.events):
            failures.append("duplicate certification event content id")
        return failures
