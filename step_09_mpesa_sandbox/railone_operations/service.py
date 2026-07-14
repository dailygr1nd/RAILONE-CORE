"""Replay-safe provider submission with stable idempotency and signed events."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Protocol

from railone_contracts.models import require_text
from railone_contracts.store import ContractStore
from railone_crypto.canonical_json import canonical_json_bytes
from railone_crypto.signature_service import ArtifactType, SignatureService
from railone_execution.models import AttemptState
from railone_execution.store import ExecutionStore

from .models import (
    OutboxDeliveryState,
    OutboxRecord,
    ProviderExecutionRequest,
    ProviderOutcome,
    ProviderSubmissionRecord,
    ProviderSubmissionResult,
    ProviderSubmissionState,
    RejectionDisposition,
)
from .store import OperationsStore


class ProviderAdapter(Protocol):
    provider_id: str
    supports_idempotency: bool

    def submit(self, request: ProviderExecutionRequest) -> ProviderSubmissionResult:
        ...


class SubmissionNotDispatchableError(RuntimeError):
    pass


class EventPublisher(Protocol):
    def publish(self, *, event_id: str, signed_event: Mapping[str, object]) -> None:
        ...


def _instant(at: datetime | None) -> datetime:
    value = at or datetime.now(timezone.utc)
    if value.tzinfo is None:
        raise ValueError("provider-operation timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def _content_id(prefix: str, payload: object) -> str:
    digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest().upper()
    return f"{prefix}-{digest[:32]}"


class ProviderSubmissionCoordinator:
    FINAL_STATES = {
        ProviderSubmissionState.ACCEPTED,
        ProviderSubmissionState.REJECTED,
        ProviderSubmissionState.UNKNOWN,
    }

    def __init__(
        self,
        *,
        signatures: SignatureService,
        contracts: ContractStore,
        executions: ExecutionStore,
        operations: OperationsStore,
        event_signing_key_id: str,
    ) -> None:
        self._signatures = signatures
        self._contracts = contracts
        self._executions = executions
        self._operations = operations
        self._event_signing_key_id = event_signing_key_id

    def prepare(
        self, *, rtt_id: str, at: datetime | None = None
    ) -> tuple[ProviderSubmissionRecord, ProviderExecutionRequest]:
        instant = _instant(at)
        attempt = self._executions.require_attempt(require_text("rtt_id", rtt_id))
        if attempt.state is not AttemptState.CREATED:
            raise SubmissionNotDispatchableError(
                "only a current CREATED RTT can be prepared"
            )
        plan = self._executions.require_plan(attempt.plan_id)
        if plan.current_rtt_id != rtt_id:
            raise SubmissionNotDispatchableError("RTT is not the current plan attempt")
        signed_rtt = attempt.signed_rtt
        rtt_check = self._signatures.verify_artifact(
            signed_rtt, expected_artifact_type=ArtifactType.RTT
        )
        if not rtt_check.valid:
            raise PermissionError(f"RTT rejected: {rtt_check.reason}")
        signed_utt = self._contracts.require_utt(attempt.utt_id)
        utt_check = self._signatures.verify_artifact(
            signed_utt, expected_artifact_type=ArtifactType.UTT
        )
        if not utt_check.valid:
            raise PermissionError(f"UTT rejected: {utt_check.reason}")
        if signed_rtt.payload["utt_payload_sha256"] != signed_utt.protected[
            "payload_sha256"
        ]:
            raise PermissionError("RTT does not bind the persisted UTT payload")

        route = signed_rtt.payload["route"]
        provider_id = require_text("provider", route["provider"]).upper()
        idempotency_material = {
            "domain": "RAILONE-PROVIDER-SUBMISSION-V1",
            "provider_id": provider_id,
            "rtt_id": rtt_id,
        }
        idempotency_key = _content_id("R1IDEM", idempotency_material)
        utt = signed_utt.payload
        request_material = {
            "idempotency_key": idempotency_key,
            "utt_id": attempt.utt_id,
            "rtt_id": rtt_id,
            "attempt_number": attempt.attempt_number,
            "provider_id": provider_id,
            "rail": route["rail"],
            "amount_minor": utt["amount_minor"],
            "currency_from": utt["currency_from"],
            "receive_amount_minor": utt["receive_amount_minor"],
            "currency_to": utt["currency_to"],
            "payer_account_reference": utt["payer"]["account_reference"],
            "beneficiary_account_reference": utt["beneficiary"]["account_reference"],
        }
        request_sha256 = hashlib.sha256(
            canonical_json_bytes(request_material)
        ).hexdigest()
        request = ProviderExecutionRequest(
            **request_material,
            request_sha256=request_sha256,
        )
        submission_id = _content_id(
            "SUB", {"rtt_id": rtt_id, "request_sha256": request_sha256}
        )
        record = ProviderSubmissionRecord(
            submission_id=submission_id,
            idempotency_key=idempotency_key,
            request_sha256=request_sha256,
            utt_id=attempt.utt_id,
            rtt_id=rtt_id,
            provider_id=provider_id,
            state=ProviderSubmissionState.PREPARED,
            dispatch_attempts=0,
            normalized_code=None,
            external_reference=None,
            rejection_disposition=None,
            provider_context=(),
            version=1,
            created_at=instant,
            updated_at=instant,
        )
        stored = self._operations.prepare(
            record,
            self._event(
                record=record,
                event_type="PROVIDER_SUBMISSION_PREPARED",
                data={"request_sha256": request_sha256},
                at=instant,
            ),
        )
        if stored.request_sha256 != request.request_sha256:
            raise RuntimeError("prepared provider request does not match stored record")
        return stored, request

    def dispatch(
        self,
        *,
        rtt_id: str,
        adapter: ProviderAdapter,
        at: datetime | None = None,
    ) -> ProviderSubmissionRecord:
        instant = _instant(at)
        record, request = self.prepare(rtt_id=rtt_id, at=instant)
        if adapter.provider_id.upper() != record.provider_id:
            raise SubmissionNotDispatchableError("adapter provider does not match RTT route")
        if record.state in self.FINAL_STATES:
            return record
        if (
            record.state is ProviderSubmissionState.DISPATCHING
            and not adapter.supports_idempotency
        ):
            return self._complete(
                record=record,
                result=ProviderSubmissionResult(
                    outcome=ProviderOutcome.UNKNOWN,
                    code="NON_IDEMPOTENT_RECOVERY_BLOCKED",
                ),
                at=instant,
            )

        dispatching = replace(
            record,
            state=ProviderSubmissionState.DISPATCHING,
            dispatch_attempts=record.dispatch_attempts + 1,
            version=record.version + 1,
            updated_at=instant,
        )
        self._operations.transition(
            previous_version=record.version,
            submission=dispatching,
            outbox=self._event(
                record=dispatching,
                event_type="PROVIDER_DISPATCH_STARTED",
                data={
                    "dispatch_attempt": dispatching.dispatch_attempts,
                    "provider_idempotency_supported": adapter.supports_idempotency,
                },
                at=instant,
            ),
        )
        try:
            result = adapter.submit(request)
        except Exception:
            result = ProviderSubmissionResult(
                outcome=ProviderOutcome.UNKNOWN,
                code="ADAPTER_EXCEPTION_OUTCOME_UNKNOWN",
            )
        return self._complete(record=dispatching, result=result, at=instant)

    def _complete(
        self,
        *,
        record: ProviderSubmissionRecord,
        result: ProviderSubmissionResult,
        at: datetime,
    ) -> ProviderSubmissionRecord:
        code = require_text("provider result code", result.code).upper()
        provider_context = _provider_context(result.provider_context)
        if result.outcome is ProviderOutcome.REJECTED:
            if result.rejection_disposition is None:
                raise ValueError("rejected provider outcome requires a disposition")
            state = ProviderSubmissionState.REJECTED
            event_type = "PROVIDER_SUBMISSION_REJECTED"
        elif result.outcome is ProviderOutcome.ACCEPTED:
            if result.rejection_disposition is not None:
                raise ValueError("accepted provider outcome cannot have rejection disposition")
            state = ProviderSubmissionState.ACCEPTED
            event_type = "PROVIDER_SUBMISSION_ACCEPTED"
        else:
            if result.rejection_disposition is not None:
                raise ValueError("unknown provider outcome cannot have rejection disposition")
            state = ProviderSubmissionState.UNKNOWN
            event_type = "PROVIDER_SUBMISSION_OUTCOME_UNKNOWN"
        updated = replace(
            record,
            state=state,
            normalized_code=code,
            external_reference=result.external_reference,
            rejection_disposition=result.rejection_disposition,
            provider_context=provider_context,
            version=record.version + 1,
            updated_at=at,
        )
        self._operations.transition(
            previous_version=record.version,
            submission=updated,
            outbox=self._event(
                record=updated,
                event_type=event_type,
                data={
                    "outcome": result.outcome.value,
                    "code": code,
                    "external_reference": result.external_reference,
                    "rejection_disposition": (
                        result.rejection_disposition.value
                        if result.rejection_disposition is not None
                        else None
                    ),
                    "provider_context": dict(provider_context),
                },
                at=at,
            ),
        )
        return updated

    def _event(
        self,
        *,
        record: ProviderSubmissionRecord,
        event_type: str,
        data: Mapping[str, object],
        at: datetime,
    ) -> OutboxRecord:
        core = {
            "event_type": event_type,
            "aggregate_type": "PROVIDER_SUBMISSION",
            "aggregate_id": record.submission_id,
            "utt_id": record.utt_id,
            "rtt_id": record.rtt_id,
            "provider_id": record.provider_id,
            "submission_version": record.version,
            "data": dict(data),
            "occurred_at": int(at.timestamp()),
        }
        event_id = _content_id("EVT", core)
        payload = {"event_id": event_id, **core}
        signed = self._signatures.sign_artifact(
            artifact_type=ArtifactType.EXECUTION_EVENT,
            payload=payload,
            key_id=self._event_signing_key_id,
            issued_at=at,
        )
        return OutboxRecord(
            event_id=event_id,
            aggregate_type="PROVIDER_SUBMISSION",
            aggregate_id=record.submission_id,
            event_type=event_type,
            signed_event=signed,
            delivery_state=OutboxDeliveryState.PENDING,
            delivery_attempts=0,
            available_at=at,
            lease_owner=None,
            lease_until=None,
            last_error=None,
            published_at=None,
            version=1,
            created_at=at,
            updated_at=at,
        )


def _provider_context(
    values: tuple[tuple[str, str], ...]
) -> tuple[tuple[str, str], ...]:
    if len(values) > 20:
        raise ValueError("provider context exceeds 20 fields")
    normalized: list[tuple[str, str]] = []
    for key, value in values:
        if (
            not isinstance(key, str) or not isinstance(value, str)
            or re.fullmatch(r"[a-z][a-z0-9_]{0,63}", key) is None
            or not value or len(value) > 256
        ):
            raise ValueError("provider context contains an invalid field")
        normalized.append((key, value))
    if len({key for key, _ in normalized}) != len(normalized):
        raise ValueError("provider context keys must be unique")
    return tuple(sorted(normalized))


class OutboxRelay:
    """At-least-once signed-event relay; consumers deduplicate by event_id."""

    def __init__(
        self,
        *,
        operations: OperationsStore,
        worker_id: str,
        lease_seconds: int = 30,
        max_attempts: int = 10,
    ) -> None:
        self._operations = operations
        self._worker_id = require_text("worker_id", worker_id)
        self._lease_seconds = lease_seconds
        self._max_attempts = max_attempts

    def publish_batch(
        self,
        *,
        publisher: EventPublisher,
        limit: int = 100,
        at: datetime | None = None,
    ) -> tuple[OutboxRecord, ...]:
        instant = _instant(at)
        claimed = self._operations.claim_outbox(
            worker_id=self._worker_id,
            at=instant,
            lease_seconds=self._lease_seconds,
            limit=limit,
        )
        outcomes = []
        for event in claimed:
            try:
                publisher.publish(
                    event_id=event.event_id,
                    signed_event=event.signed_event.to_dict(),
                )
            except Exception as exc:
                delay_seconds = min(300, 2 ** min(event.delivery_attempts, 8))
                outcomes.append(
                    self._operations.reschedule(
                        event_id=event.event_id,
                        worker_id=self._worker_id,
                        at=instant,
                        available_at=instant + timedelta(seconds=delay_seconds),
                        error=type(exc).__name__,
                        max_attempts=self._max_attempts,
                    )
                )
            else:
                outcomes.append(
                    self._operations.mark_published(
                        event_id=event.event_id,
                        worker_id=self._worker_id,
                        at=instant,
                    )
                )
        return tuple(outcomes)
