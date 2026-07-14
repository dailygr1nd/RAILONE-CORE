"""Replay-safe simulated provider effects.

The broker changes economic effects only. RailOne still signs UTT/RTT
artifacts, enforces idempotency, blocks unknown outcomes and requires callback
evidence for settlement.
"""

from __future__ import annotations

import hashlib
import json
from threading import RLock

from railone_crypto.canonical_json import canonical_json_bytes
from railone_operations import (
    ProviderExecutionRequest, ProviderOutcome, ProviderSubmissionResult,
    RejectionDisposition,
)

from .metrics import MetricsRegistry
from .models import EffectScenario, ProviderEffectRecord, ScheduledProviderEffect
from .store import InMemorySandboxEffectStore, SandboxEffectStore


class SandboxEffectBroker:
    def __init__(
        self, *, metrics: MetricsRegistry | None = None,
        effect_store: SandboxEffectStore | None = None,
    ) -> None:
        self._lock = RLock()
        self._metrics = metrics or MetricsRegistry()
        self._scenarios: dict[str, EffectScenario] = {}
        self._submissions: dict[tuple[str, str], tuple[str, ProviderSubmissionResult]] = {}
        self._effect_store = effect_store or InMemorySandboxEffectStore()

    def set_scenario(self, *, rtt_id: str, scenario: EffectScenario) -> None:
        with self._lock:
            if any(key[1] == rtt_id for key in self._submissions):
                raise RuntimeError("scenario cannot change after provider submission")
            self._scenarios[rtt_id] = scenario

    def submit(self, request: ProviderExecutionRequest) -> ProviderSubmissionResult:
        self._validate_synthetic(request)
        key = (request.provider_id, request.idempotency_key)
        with self._lock:
            existing = self._submissions.get(key)
            if existing is not None:
                if existing[0] != request.request_sha256:
                    raise RuntimeError("simulator idempotency material changed")
                self._metrics.increment("railone_sandbox_submit_replay_total", provider=request.provider_id)
                return existing[1]
            scenario = self._scenarios.get(request.rtt_id, EffectScenario.SUCCESS)
            result = self._result(request, scenario)
            self._submissions[key] = (request.request_sha256, result)
            self._metrics.increment(
                "railone_sandbox_submissions_total", provider=request.provider_id,
                outcome=result.outcome.value, scenario=scenario.value,
            )
            return result

    def advance(self, *, ticks: int = 1) -> tuple[ScheduledProviderEffect, ...]:
        records = self._effect_store.advance_and_claim(
            worker_id="inline-sandbox-inspector", ticks=ticks,
            lease_ticks=1, limit=1000,
        )
        due = []
        for record in records:
            item = record.effect
            self._effect_store.mark_delivered(
                effect_id=item.effect_id, worker_id="inline-sandbox-inspector"
            )
            due.append(item)
            self._metrics.increment(
                "railone_sandbox_effects_total", provider=item.provider_id,
                effect_type=item.effect_type,
            )
        return tuple(due)

    def claim_due(
        self, *, worker_id: str, ticks: int = 1, lease_ticks: int = 2,
        limit: int = 100,
    ) -> tuple[ProviderEffectRecord, ...]:
        return self._effect_store.advance_and_claim(
            worker_id=worker_id, ticks=ticks, lease_ticks=lease_ticks, limit=limit,
        )

    def mark_delivered(self, *, effect_id: str, worker_id: str) -> None:
        self._effect_store.mark_delivered(effect_id=effect_id, worker_id=worker_id)

    def reschedule(
        self, *, effect_id: str, worker_id: str, delay_ticks: int,
        error: str, max_attempts: int,
    ) -> None:
        self._effect_store.reschedule(
            effect_id=effect_id, worker_id=worker_id,
            delay_ticks=delay_ticks, error=error, max_attempts=max_attempts,
        )
        self._metrics.increment("railone_sandbox_effect_requeues_total")

    @property
    def current_tick(self) -> int:
        return self._effect_store.current_tick()

    def _result(self, request: ProviderExecutionRequest, scenario: EffectScenario) -> ProviderSubmissionResult:
        if scenario is EffectScenario.REJECTED_RETRYABLE:
            return ProviderSubmissionResult(
                outcome=ProviderOutcome.REJECTED, code="SIM_PROVIDER_TEMPORARY",
                rejection_disposition=RejectionDisposition.RETRYABLE,
            )
        if scenario is EffectScenario.REJECTED_TERMINAL:
            return ProviderSubmissionResult(
                outcome=ProviderOutcome.REJECTED, code="SIM_PROVIDER_TERMINAL",
                rejection_disposition=RejectionDisposition.TERMINAL,
            )
        if scenario is EffectScenario.UNKNOWN_AFTER_SEND:
            return ProviderSubmissionResult(
                outcome=ProviderOutcome.UNKNOWN, code="SIM_OUTCOME_UNKNOWN",
            )
        external = "SIMREF-" + hashlib.sha256(
            f"{request.provider_id}:{request.rtt_id}".encode("utf-8")
        ).hexdigest().upper()[:24]
        originator = "SIMORG-" + hashlib.sha256(request.idempotency_key.encode("utf-8")).hexdigest().upper()[:20]
        result = ProviderSubmissionResult(
            outcome=ProviderOutcome.ACCEPTED, code="SIM_ACCEPTED_FOR_PROCESSING",
            external_reference=external,
            provider_context=(
                ("originator_conversation_id", originator),
                ("amount_minor", str(request.amount_minor)),
            ),
        )
        if scenario is EffectScenario.TIMEOUT_THEN_SUCCESS:
            self._schedule(request, external, originator, "TIMEOUT", 1)
            self._schedule(request, external, originator, "SETTLED", 2)
        else:
            self._schedule(request, external, originator, "SETTLED", 1)
        return result

    def _schedule(
        self, request: ProviderExecutionRequest, external: str, originator: str,
        effect_type: str, offset: int,
    ) -> None:
        transaction_id = "SIMTX-" + hashlib.sha256(
            f"{external}:{effect_type}".encode("utf-8")
        ).hexdigest().upper()[:20]
        if request.provider_id == "MPESA-KE":
            result_code = 0 if effect_type == "SETTLED" else 2001
            payload_object = {"Result": {
                "ResultType": 0, "ResultCode": result_code,
                "ResultDesc": "Simulated settlement" if result_code == 0 else "Simulated timeout",
                "OriginatorConversationID": originator,
                "ConversationID": external,
                "TransactionID": transaction_id if result_code == 0 else None,
                "ResultParameters": {"ResultParameter": [
                    {"Key": "TransactionAmount", "Value": request.amount_minor // 100},
                    {"Key": "TransactionReceipt", "Value": transaction_id},
                ]} if result_code == 0 else None,
            }}
        else:
            payload_object = {
                "provider": request.provider_id, "event": effect_type,
                "external_reference": external, "transaction_id": transaction_id,
                "rtt_id": request.rtt_id, "amount_minor": request.amount_minor,
                "currency": request.currency_from,
            }
        payload = json.dumps(payload_object, separators=(",", ":"), sort_keys=True).encode("utf-8")
        effect_id = "SIMEFF-" + hashlib.sha256(canonical_json_bytes({
            "provider": request.provider_id, "rtt_id": request.rtt_id,
            "effect": effect_type, "offset": offset,
        })).hexdigest().upper()[:24]
        effect = ScheduledProviderEffect(
            effect_id=effect_id, provider_id=request.provider_id, rtt_id=request.rtt_id,
            external_reference=external, effect_type=effect_type,
            provider_code="0" if effect_type == "SETTLED" else "TIMEOUT",
            due_tick=self.current_tick + offset, payload=payload,
        )
        self._effect_store.schedule(ProviderEffectRecord(
            effect=effect, available_tick=effect.due_tick
        ))

    @staticmethod
    def _validate_synthetic(request: ProviderExecutionRequest) -> None:
        if not request.provider_id.startswith("SIM-") and request.provider_id not in {"MPESA-KE", "BANK-KE"}:
            raise ValueError("sandbox provider is outside the allowlist")
        if not request.payer_account_reference.startswith("SIM-"):
            raise PermissionError("sandbox refuses non-synthetic payer endpoints")
        if not request.beneficiary_account_reference.startswith("SIM-"):
            raise PermissionError("sandbox refuses non-synthetic beneficiary endpoints")
