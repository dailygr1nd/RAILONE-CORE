"""Authenticated M-PESA callback normalization and RTT finality."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Protocol

from railone_crypto.canonical_json import canonical_json_bytes
from railone_execution import (
    AttemptState,
    FailureDisposition,
    RttAttemptService,
)
from railone_execution.store import ExecutionStore
from railone_operations.store import OperationsStore
from railone_notifications import SettlementNotificationService

from .models import CallbackApplicationResult, CallbackState
from .store import CallbackInboxStore


class CallbackSecretProvider(Protocol):
    def get_secret(self) -> bytes: ...


class EnvironmentCallbackSecretProvider:
    def get_secret(self) -> bytes:
        value = os.environ.get("RAILONE_MPESA_INGRESS_HMAC_SECRET", "")
        secret = value.encode("utf-8")
        if len(secret) < 32:
            raise RuntimeError("M-PESA ingress HMAC secret must contain at least 32 bytes")
        return secret


class MpesaIngressAuthenticator:
    """Verify HMAC added by RailOne's trusted callback ingress gateway.

    This is not represented as a native Safaricom callback signature.
    """

    def __init__(self, secrets: CallbackSecretProvider) -> None:
        self._secrets = secrets

    def verify(self, *, raw_body: bytes, signature: str) -> bool:
        supplied = signature.removeprefix("sha256=").strip().lower()
        if len(supplied) != 64:
            return False
        expected = hmac.new(
            self._secrets.get_secret(), raw_body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, supplied)


class MpesaCallbackProcessor:
    provider_id = "MPESA-KE"

    def __init__(
        self,
        *,
        authenticator: MpesaIngressAuthenticator,
        inbox: CallbackInboxStore,
        operations: OperationsStore,
        executions: ExecutionStore,
        attempts: RttAttemptService,
        settlements: SettlementNotificationService | None = None,
        retryable_result_codes: frozenset[int] = frozenset(),
    ) -> None:
        self._authenticator = authenticator
        self._inbox = inbox
        self._operations = operations
        self._executions = executions
        self._attempts = attempts
        self._settlements = settlements
        self._retryable_codes = retryable_result_codes

    def process_result(
        self, *, raw_body: bytes, ingress_signature: str, at: datetime | None = None
    ) -> CallbackApplicationResult:
        return self._process(
            callback_type="RESULT", raw_body=raw_body,
            ingress_signature=ingress_signature, at=at,
        )

    def process_timeout(
        self, *, raw_body: bytes, ingress_signature: str, at: datetime | None = None
    ) -> CallbackApplicationResult:
        return self._process(
            callback_type="TIMEOUT", raw_body=raw_body,
            ingress_signature=ingress_signature, at=at,
        )

    def _process(
        self,
        *,
        callback_type: str,
        raw_body: bytes,
        ingress_signature: str,
        at: datetime | None,
    ) -> CallbackApplicationResult:
        instant = at or datetime.now(timezone.utc)
        if instant.tzinfo is None:
            raise ValueError("callback timestamp must be timezone-aware")
        instant = instant.astimezone(timezone.utc)
        if len(raw_body) > 65_536:
            raise ValueError("M-PESA callback exceeds 64 KiB")
        raw_hash = hashlib.sha256(raw_body).hexdigest()
        if not self._authenticator.verify(
            raw_body=raw_body, signature=ingress_signature
        ):
            event_id = f"MPESA-REJECTED-{raw_hash.upper()[:32]}"
            self._inbox.ingest(
                provider_id=self.provider_id, provider_event_id=event_id,
                payload_sha256=raw_hash, normalized_payload={},
                signature_valid=False, received_at=instant,
            )
            raise PermissionError("M-PESA callback ingress authentication failed")
        normalized = _normalize(raw_body)
        conversation_id = normalized["conversation_id"]
        submission = self._operations.find_by_external_reference(
            self.provider_id, conversation_id
        )
        if submission is None:
            raise LookupError("M-PESA callback has no matching provider submission")
        context = dict(submission.provider_context)
        if context.get("originator_conversation_id") != normalized["originator_conversation_id"]:
            raise PermissionError("M-PESA callback correlation mismatch")
        result_code = normalized["result_code"]
        success = callback_type == "RESULT" and result_code == 0
        if success:
            _verify_success_evidence(normalized, context)
        event_id = f"MPESA-{callback_type}-{conversation_id}"
        payload_hash = hashlib.sha256(canonical_json_bytes(normalized)).hexdigest()
        record, duplicate = self._inbox.ingest(
            provider_id=self.provider_id, provider_event_id=event_id,
            payload_sha256=payload_hash, normalized_payload=normalized,
            signature_valid=True, received_at=instant,
        )
        if record.state is CallbackState.APPLIED:
            return CallbackApplicationResult(
                provider_event_id=event_id,
                rtt_id=submission.rtt_id,
                disposition="ALREADY_APPLIED", duplicate=True,
            )
        attempt = self._executions.require_attempt(submission.rtt_id)
        if callback_type == "TIMEOUT":
            disposition = "RECONCILIATION_REQUIRED"
            if attempt.state is AttemptState.CREATED:
                self._attempts.record_failure(
                    rtt_id=attempt.rtt_id,
                    failure_code="MPESA_CALLBACK_TIMEOUT",
                    disposition=FailureDisposition.RECONCILIATION_REQUIRED,
                    actual_cost_minor=0,
                    at=instant,
                )
            elif attempt.state is not AttemptState.RECONCILIATION_REQUIRED:
                raise RuntimeError("timeout callback conflicts with finalized RTT")
        elif success:
            disposition = "CONFIRMED_SUCCESS"
            if attempt.state is AttemptState.CREATED:
                self._attempts.record_success(
                    rtt_id=attempt.rtt_id, actual_cost_minor=0, at=instant
                )
            elif attempt.state is AttemptState.RECONCILIATION_REQUIRED:
                self._attempts.resolve_reconciliation(
                    rtt_id=attempt.rtt_id, succeeded=True,
                    actual_cost_minor=0, at=instant,
                )
            elif attempt.state is not AttemptState.SUCCEEDED:
                raise RuntimeError("success callback conflicts with finalized RTT")
            if self._settlements is not None:
                self._settlements.confirm_provider_settlement(
                    utt_id=submission.utt_id,
                    provider_id=self.provider_id,
                    provider_transaction_id=str(normalized["transaction_id"]),
                    callback_event_id=event_id,
                    at=instant,
                )
        else:
            retryable = result_code in self._retryable_codes
            failure_disposition = (
                FailureDisposition.RETRYABLE
                if retryable else FailureDisposition.TERMINAL
            )
            disposition = (
                "CONFIRMED_RETRYABLE_FAILURE" if retryable else "CONFIRMED_TERMINAL_FAILURE"
            )
            code = f"MPESA_RESULT_{result_code}"
            if attempt.state is AttemptState.CREATED:
                self._attempts.record_failure(
                    rtt_id=attempt.rtt_id, failure_code=code,
                    disposition=failure_disposition,
                    actual_cost_minor=0, at=instant,
                )
            elif attempt.state is AttemptState.RECONCILIATION_REQUIRED:
                self._attempts.resolve_reconciliation(
                    rtt_id=attempt.rtt_id, succeeded=False,
                    failure_code=code, failure_disposition=failure_disposition,
                    actual_cost_minor=0, at=instant,
                )
            elif attempt.state is not AttemptState.FAILED:
                raise RuntimeError("failure callback conflicts with finalized RTT")
        self._inbox.mark_applied(
            provider_id=self.provider_id, provider_event_id=event_id, at=instant
        )
        return CallbackApplicationResult(
            provider_event_id=event_id, rtt_id=submission.rtt_id,
            disposition=disposition, duplicate=duplicate,
        )


def _normalize(raw_body: bytes) -> dict[str, object]:
    try:
        payload = json.loads(raw_body.decode("utf-8"))
        result = payload["Result"]
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError("invalid M-PESA callback envelope") from exc
    if not isinstance(result, Mapping):
        raise ValueError("M-PESA Result must be an object")
    conversation_id = _text(result, "ConversationID", 128)
    originator_id = _text(result, "OriginatorConversationID", 128)
    transaction_id = result.get("TransactionID")
    if transaction_id is not None and (
        not isinstance(transaction_id, str) or len(transaction_id) > 128
    ):
        raise ValueError("M-PESA TransactionID is invalid")
    result_code = result.get("ResultCode")
    if isinstance(result_code, bool) or not isinstance(result_code, int):
        raise ValueError("M-PESA ResultCode must be an integer")
    description = result.get("ResultDesc", "")
    if not isinstance(description, str):
        raise ValueError("M-PESA ResultDesc must be text")
    parameters = _allowed_parameters(result.get("ResultParameters"))
    return {
        "conversation_id": conversation_id,
        "originator_conversation_id": originator_id,
        "transaction_id": transaction_id,
        "result_code": result_code,
        "result_description": description[:256],
        "parameters": parameters,
    }


def _text(value: Mapping[str, object], key: str, maximum: int) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item or len(item) > maximum:
        raise ValueError(f"M-PESA {key} is invalid")
    return item


def _allowed_parameters(value: object) -> dict[str, object]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("M-PESA ResultParameters must be an object")
    items = value.get("ResultParameter", ())
    if not isinstance(items, list):
        raise ValueError("M-PESA ResultParameter must be an array")
    allowed = {"TransactionAmount", "TransactionReceipt"}
    result: dict[str, object] = {}
    for item in items:
        if not isinstance(item, Mapping):
            raise ValueError("M-PESA result parameter must be an object")
        key = item.get("Key")
        if key in allowed:
            parameter = item.get("Value")
            if isinstance(parameter, bool) or not isinstance(parameter, str | int):
                raise ValueError("M-PESA result parameter value is invalid")
            result[str(key)] = parameter
    return result


def _verify_success_evidence(
    normalized: Mapping[str, object], context: Mapping[str, str]
) -> None:
    transaction_id = normalized["transaction_id"]
    if not isinstance(transaction_id, str) or not transaction_id:
        raise ValueError("successful M-PESA callback omitted TransactionID")
    expected_amount = context.get("amount_minor")
    if expected_amount is None or not expected_amount.isdigit():
        raise RuntimeError("M-PESA submission is missing its expected amount")
    parameters = normalized["parameters"]
    if not isinstance(parameters, Mapping):
        raise ValueError("M-PESA success parameters are invalid")
    amount = parameters.get("TransactionAmount")
    if isinstance(amount, bool) or not (
        isinstance(amount, int) or isinstance(amount, str) and amount.isdigit()
    ):
        raise ValueError("M-PESA success omitted an integer TransactionAmount")
    if int(amount) * 100 != int(expected_amount):
        raise PermissionError("M-PESA callback amount does not match the dispatched request")
    receipt = parameters.get("TransactionReceipt")
    if receipt is not None and receipt != transaction_id:
        raise PermissionError("M-PESA callback receipt does not match TransactionID")
