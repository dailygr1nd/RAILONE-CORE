from __future__ import annotations

import hashlib
import hmac
import json
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from railone_callbacks import (
    CallbackPayloadConflictError,
    InMemoryCallbackInboxStore,
    MpesaCallbackProcessor,
    MpesaIngressAuthenticator,
)
from railone_crypto.signature_service import SignatureEnvelope
from railone_execution import (
    AttemptState,
    ExecutionPlan,
    InMemoryExecutionStore,
    PlanStatus,
    RttAttemptRecord,
    RttAttemptService,
)
from railone_operations import (
    InMemoryOperationsStore,
    OutboxDeliveryState,
    OutboxRecord,
    ProviderSubmissionRecord,
    ProviderSubmissionState,
)


SECRET = b"railone-test-ingress-secret-at-least-32-bytes"


class FixedSecret:
    def get_secret(self) -> bytes:
        return SECRET


class RecordingSettlements:
    def __init__(self) -> None:
        self.calls = []

    def confirm_provider_settlement(self, **kwargs):
        self.calls.append(kwargs)


class ContractPresence:
    def require_utt(self, utt_id: str):
        if utt_id != "UTT-001":
            raise LookupError(utt_id)
        return object()


def envelope(
    result_code: int,
    *,
    transaction_id: str | None = None,
    transaction_amount: int | None = None,
    description: str = "ok",
) -> bytes:
    result: dict[str, object] = {
        "ConversationID": "AG_001",
        "OriginatorConversationID": "R1_ORIGIN_001",
        "ResultCode": result_code,
        "ResultDesc": description,
    }
    if transaction_id is not None:
        result["TransactionID"] = transaction_id
    if transaction_amount is not None:
        result["ResultParameters"] = {
            "ResultParameter": [
                {"Key": "TransactionAmount", "Value": transaction_amount},
                {"Key": "TransactionReceipt", "Value": transaction_id},
            ]
        }
    return json.dumps({"Result": result}, separators=(",", ":")).encode()


def signature(body: bytes) -> str:
    return "sha256=" + hmac.new(SECRET, body, hashlib.sha256).hexdigest()


class MpesaCallbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 7, 14, 16, 0, tzinfo=timezone.utc)
        contracts = ContractPresence()
        self.executions = InMemoryExecutionStore(contracts)
        birth_plan = ExecutionPlan(
            plan_id="PLAN-001", utt_id="UTT-001", ranked_routes=(),
            remaining_route_ids=(), failures=(), attempts_used=0, max_attempts=1,
            routing_budget_minor=0, routing_cost_spent_minor=0,
            current_rtt_id=None, previous_rtt_id=None, previous_route_id=None,
            status=PlanStatus.ACTIVE, successful_route_id=None, version=1,
            created_at=self.now, updated_at=self.now,
        )
        self.executions.create_plan(birth_plan)
        attempt = RttAttemptRecord(
            rtt_id="RTT-001", utt_id="UTT-001", plan_id="PLAN-001",
            attempt_number=1, route_id="MPESA-B2C",
            signed_rtt=SignatureEnvelope(
                protected={"payload_sha256": "a" * 64}, payload={}, signature="test"
            ),
            state=AttemptState.CREATED, failure_code=None, actual_cost_minor=None,
            created_at=self.now, updated_at=self.now,
        )
        self.executions.commit_start(
            previous_version=1,
            plan=replace(
                birth_plan, attempts_used=1, current_rtt_id="RTT-001",
                version=2, updated_at=self.now,
            ),
            attempt=attempt,
        )
        self.operations = InMemoryOperationsStore()
        submission = ProviderSubmissionRecord(
            submission_id="SUB-001", idempotency_key="R1IDEM-001",
            request_sha256="b" * 64, utt_id="UTT-001", rtt_id="RTT-001",
            provider_id="MPESA-KE", state=ProviderSubmissionState.ACCEPTED,
            dispatch_attempts=1, normalized_code="MPESA_ACCEPTED_FOR_PROCESSING",
            external_reference="AG_001", rejection_disposition=None,
            provider_context=(
                ("amount_minor", "250000"),
                ("originator_conversation_id", "R1_ORIGIN_001"),
            ),
            version=3, created_at=self.now, updated_at=self.now,
        )
        self.operations.prepare(
            submission,
            OutboxRecord(
                event_id="EVT-001", aggregate_type="PROVIDER_SUBMISSION",
                aggregate_id="SUB-001", event_type="TEST",
                signed_event=SignatureEnvelope(
                    protected={"payload_sha256": "c" * 64}, payload={}, signature="test"
                ),
                delivery_state=OutboxDeliveryState.PENDING, delivery_attempts=0,
                available_at=self.now, lease_owner=None, lease_until=None,
                last_error=None, published_at=None, version=1,
                created_at=self.now, updated_at=self.now,
            ),
        )
        self.inbox = InMemoryCallbackInboxStore()
        attempts = RttAttemptService(
            signatures=None, contracts=None, executions=self.executions,
            rtt_signing_key_id="unused",
        )
        self.settlements = RecordingSettlements()
        self.processor = MpesaCallbackProcessor(
            authenticator=MpesaIngressAuthenticator(FixedSecret()),
            inbox=self.inbox, operations=self.operations,
            executions=self.executions, attempts=attempts,
            settlements=self.settlements,
        )

    def test_authenticated_success_finalizes_exactly_once(self) -> None:
        body = envelope(0, transaction_id="TXN-001", transaction_amount=2500)

        first = self.processor.process_result(
            raw_body=body, ingress_signature=signature(body), at=self.now
        )
        second = self.processor.process_result(
            raw_body=body, ingress_signature=signature(body),
            at=self.now + timedelta(seconds=1),
        )

        self.assertEqual(first.disposition, "CONFIRMED_SUCCESS")
        self.assertEqual(second.disposition, "ALREADY_APPLIED")
        self.assertTrue(second.duplicate)
        self.assertEqual(second.rtt_id, "RTT-001")
        self.assertEqual(
            self.executions.require_attempt("RTT-001").state,
            AttemptState.SUCCEEDED,
        )
        self.assertEqual(
            self.executions.require_plan("PLAN-001").status,
            PlanStatus.FINALIZED,
        )
        self.assertEqual(len(self.settlements.calls), 1)
        self.assertEqual(
            self.settlements.calls[0]["provider_transaction_id"], "TXN-001"
        )

    def test_invalid_ingress_hmac_cannot_change_execution_state(self) -> None:
        body = envelope(0, transaction_id="TXN-001", transaction_amount=2500)

        with self.assertRaises(PermissionError):
            self.processor.process_result(
                raw_body=body, ingress_signature="sha256=" + "0" * 64, at=self.now
            )

        self.assertEqual(
            self.executions.require_attempt("RTT-001").state,
            AttemptState.CREATED,
        )

    def test_same_provider_event_id_with_changed_material_is_rejected(self) -> None:
        body = envelope(0, transaction_id="TXN-001", transaction_amount=2500)
        self.processor.process_result(
            raw_body=body, ingress_signature=signature(body), at=self.now
        )
        changed = envelope(
            0, transaction_id="TXN-001", transaction_amount=2500,
            description="changed",
        )

        with self.assertRaises(CallbackPayloadConflictError):
            self.processor.process_result(
                raw_body=changed, ingress_signature=signature(changed),
                at=self.now + timedelta(seconds=1),
            )

    def test_timeout_blocks_reroute_until_later_success_reconciles(self) -> None:
        timeout = envelope(1, description="queue timeout")
        timeout_result = self.processor.process_timeout(
            raw_body=timeout, ingress_signature=signature(timeout), at=self.now
        )

        self.assertEqual(timeout_result.disposition, "RECONCILIATION_REQUIRED")
        self.assertEqual(
            self.executions.require_plan("PLAN-001").status,
            PlanStatus.RECONCILIATION_REQUIRED,
        )
        success = envelope(
            0, transaction_id="TXN-LATE-001", transaction_amount=2500
        )
        result = self.processor.process_result(
            raw_body=success, ingress_signature=signature(success),
            at=self.now + timedelta(minutes=1),
        )

        self.assertEqual(result.disposition, "CONFIRMED_SUCCESS")
        self.assertEqual(
            self.executions.require_plan("PLAN-001").status,
            PlanStatus.FINALIZED,
        )

    def test_success_without_transaction_id_is_not_accepted_as_finality(self) -> None:
        body = envelope(0)

        with self.assertRaises(ValueError):
            self.processor.process_result(
                raw_body=body, ingress_signature=signature(body), at=self.now
            )

        self.assertEqual(
            self.executions.require_attempt("RTT-001").state,
            AttemptState.CREATED,
        )

        corrected = envelope(
            0, transaction_id="TXN-001", transaction_amount=2500
        )
        result = self.processor.process_result(
            raw_body=corrected, ingress_signature=signature(corrected),
            at=self.now + timedelta(seconds=1),
        )
        self.assertEqual(result.disposition, "CONFIRMED_SUCCESS")

    def test_success_amount_mismatch_cannot_finalize_the_rtt(self) -> None:
        body = envelope(0, transaction_id="TXN-001", transaction_amount=2499)

        with self.assertRaises(PermissionError):
            self.processor.process_result(
                raw_body=body, ingress_signature=signature(body), at=self.now
            )

        self.assertEqual(
            self.executions.require_attempt("RTT-001").state,
            AttemptState.CREATED,
        )


if __name__ == "__main__":
    unittest.main()
