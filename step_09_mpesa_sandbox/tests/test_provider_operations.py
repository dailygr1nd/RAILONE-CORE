from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from railone_authority import ExecutionAuthorityService
from railone_contracts import (
    ActorReference,
    ContextType,
    InMemoryContractStore,
    OriginContext,
    PaymentPurpose,
    QuoteAcceptanceCommand,
    QuoteAcceptanceService,
    QuoteService,
    QuoteTerms,
)
from railone_crypto.key_provider import InMemoryEd25519KeyProvider, KeyPurpose
from railone_crypto.signature_service import ArtifactType, SignatureService
from railone_execution import (
    ExecutionPlanningService,
    InMemoryExecutionStore,
    LinkStatus,
    RouteCandidate,
    RttAttemptService,
)
from railone_operations import (
    InMemoryOperationsStore,
    OutboxDeliveryState,
    OutboxRelay,
    ProviderOutcome,
    ProviderSubmissionCoordinator,
    ProviderSubmissionResult,
    ProviderSubmissionState,
    RejectionDisposition,
)


class FakeProviderAdapter:
    def __init__(
        self,
        *,
        result: ProviderSubmissionResult | None = None,
        raises: bool = False,
        supports_idempotency: bool = True,
    ) -> None:
        self.provider_id = "PROVIDER-FAST"
        self.supports_idempotency = supports_idempotency
        self.result = result or ProviderSubmissionResult(
            outcome=ProviderOutcome.ACCEPTED,
            code="ACCEPTED_FOR_PROCESSING",
            external_reference="PROVIDER-REF-001",
        )
        self.raises = raises
        self.calls = 0
        self.last_request = None

    def submit(self, request):
        self.calls += 1
        self.last_request = request
        if self.raises:
            raise TimeoutError("simulated timeout after provider call")
        return self.result


class FakeEventPublisher:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.events = []

    def publish(self, *, event_id, signed_event):
        if self.fail:
            raise ConnectionError("simulated event transport failure")
        self.events.append((event_id, signed_event))


class ProviderOperationsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 7, 14, 15, 0, tzinfo=timezone.utc)
        keys = InMemoryEd25519KeyProvider()
        keys.generate(
            key_id="R1CORE:quote:2026-01",
            owner_id="R1CORE",
            purpose=KeyPurpose.QUOTE_SIGNING,
            not_before=self.now - timedelta(days=1),
            not_after=self.now + timedelta(days=90),
        )
        keys.generate(
            key_id="R1CORE:execution:2026-01",
            owner_id="R1CORE",
            purpose=KeyPurpose.EXECUTION_SIGNING,
            not_before=self.now - timedelta(days=1),
            not_after=self.now + timedelta(days=90),
        )
        self.signatures = SignatureService(keys)
        self.contracts = InMemoryContractStore()
        self.executions = InMemoryExecutionStore(self.contracts)
        self.operations = InMemoryOperationsStore()
        self.rtt_id = self._create_current_rtt()
        self.coordinator = ProviderSubmissionCoordinator(
            signatures=self.signatures,
            contracts=self.contracts,
            executions=self.executions,
            operations=self.operations,
            event_signing_key_id="R1CORE:execution:2026-01",
        )

    def _create_current_rtt(self) -> str:
        quote = QuoteService(self.signatures).issue_quote(
            terms=QuoteTerms(
                request_id="REQ-OPS-001",
                payer=ActorReference("MERCHANT", "MER002", "PAYER-SECRET-REF"),
                beneficiary=ActorReference(
                    "SUPPLIER", "SUP001", "BENEFICIARY-SECRET-REF"
                ),
                purpose=PaymentPurpose.SUPPLIER_PAYMENT,
                amount_minor=250_000,
                currency_from="KES",
                receive_amount_minor=247_500,
                currency_to="KES",
                total_fee_minor=2_500,
                routing_budget_minor=1_000,
                fx_rate="1.000000",
                corridor_id="KE-DOMESTIC",
                service_level="STANDARD",
                routing_policy_id="POLICY-KE-OPS",
                pricing_version="2026-07",
            ),
            signing_key_id="R1CORE:quote:2026-01",
            issued_at=self.now,
            expires_at=self.now + timedelta(minutes=1),
        )
        contract = QuoteAcceptanceService(
            signatures=self.signatures,
            authority=ExecutionAuthorityService(self.signatures),
            store=self.contracts,
            utt_signing_key_id="R1CORE:execution:2026-01",
            authority_signing_key_id="R1CORE:execution:2026-01",
        ).accept(
            QuoteAcceptanceCommand(
                signed_quote=quote,
                origin=OriginContext(
                    origin_system="AVIA",
                    origin_intent_id="AVIA-SUPPLIER-OPS-001",
                    context_type=ContextType.MERCHANT,
                    purpose=PaymentPurpose.SUPPLIER_PAYMENT,
                    merchant_id="MER002",
                    branch_id="BR001",
                ),
                authorization_method="MERCHANT_ACTOR_ATTESTATION",
                authorization_reference="AUTH-OPS-001",
                idempotency_key="IDEM-OPS-001",
            ),
            at=self.now + timedelta(seconds=10),
        ).contract
        route = RouteCandidate(
            route_id="FAST",
            source_institution_id="INST-SOURCE",
            destination_institution_id="INST-DEST",
            rail="MOBILE_MONEY",
            provider="PROVIDER-FAST",
            adapter="provider-fast-v1",
            currency_from="KES",
            currency_to="KES",
            min_amount_minor=100,
            max_amount_minor=5_000_000,
            latency_ms=100,
            congestion_bps=500,
            liquidity_capacity_minor=2_000_000,
            throughput_headroom_bps=9_000,
            speed_bps=9_500,
            estimated_cost_minor=100,
            link_status=LinkStatus.UP,
            telemetry_observed_at=self.now,
            telemetry_expires_at=self.now + timedelta(minutes=5),
        )
        ExecutionPlanningService(
            signatures=self.signatures,
            contracts=self.contracts,
            executions=self.executions,
        ).build_plan(
            utt_id=contract.utt_id,
            candidates=(route,),
            at=self.now + timedelta(seconds=20),
        )
        attempt = RttAttemptService(
            signatures=self.signatures,
            contracts=self.contracts,
            executions=self.executions,
            rtt_signing_key_id="R1CORE:execution:2026-01",
        ).start_next(
            utt_id=contract.utt_id,
            at=self.now + timedelta(seconds=21),
        )
        return attempt.rtt_id

    def test_preparation_is_idempotent_and_uses_stable_provider_key(self) -> None:
        first, first_request = self.coordinator.prepare(
            rtt_id=self.rtt_id, at=self.now + timedelta(seconds=22)
        )
        second, second_request = self.coordinator.prepare(
            rtt_id=self.rtt_id, at=self.now + timedelta(seconds=30)
        )

        self.assertEqual(first, second)
        self.assertEqual(first_request.idempotency_key, second_request.idempotency_key)
        self.assertEqual(first_request.request_sha256, second_request.request_sha256)

    def test_accepted_submission_is_not_dispatched_twice(self) -> None:
        adapter = FakeProviderAdapter()
        first = self.coordinator.dispatch(
            rtt_id=self.rtt_id,
            adapter=adapter,
            at=self.now + timedelta(seconds=22),
        )
        second = self.coordinator.dispatch(
            rtt_id=self.rtt_id,
            adapter=adapter,
            at=self.now + timedelta(seconds=23),
        )

        self.assertEqual(first.state, ProviderSubmissionState.ACCEPTED)
        self.assertEqual(second, first)
        self.assertEqual(adapter.calls, 1)
        self.assertEqual(adapter.last_request.amount_minor, 250_000)

    def test_adapter_exception_becomes_unknown_not_retryable_failure(self) -> None:
        adapter = FakeProviderAdapter(raises=True)
        record = self.coordinator.dispatch(
            rtt_id=self.rtt_id,
            adapter=adapter,
            at=self.now + timedelta(seconds=22),
        )

        self.assertEqual(record.state, ProviderSubmissionState.UNKNOWN)
        self.assertEqual(record.normalized_code, "ADAPTER_EXCEPTION_OUTCOME_UNKNOWN")
        self.assertIsNone(record.rejection_disposition)
        self.coordinator.dispatch(
            rtt_id=self.rtt_id,
            adapter=adapter,
            at=self.now + timedelta(seconds=23),
        )
        self.assertEqual(adapter.calls, 1)

    def test_non_idempotent_dispatch_recovery_blocks_a_second_provider_call(self) -> None:
        prepared, _ = self.coordinator.prepare(
            rtt_id=self.rtt_id, at=self.now + timedelta(seconds=22)
        )
        # Model a worker crash after the durable DISPATCHING transition but
        # before RailOne persisted the provider response.
        self.operations._submissions_by_rtt[self.rtt_id] = replace(
            prepared,
            state=ProviderSubmissionState.DISPATCHING,
            dispatch_attempts=1,
            version=prepared.version + 1,
            updated_at=self.now + timedelta(seconds=22),
        )
        adapter = FakeProviderAdapter(supports_idempotency=False)

        recovered = self.coordinator.dispatch(
            rtt_id=self.rtt_id,
            adapter=adapter,
            at=self.now + timedelta(seconds=23),
        )

        self.assertEqual(recovered.state, ProviderSubmissionState.UNKNOWN)
        self.assertEqual(recovered.normalized_code, "NON_IDEMPOTENT_RECOVERY_BLOCKED")
        self.assertEqual(adapter.calls, 0)

    def test_known_rejection_carries_explicit_retry_disposition(self) -> None:
        adapter = FakeProviderAdapter(
            result=ProviderSubmissionResult(
                outcome=ProviderOutcome.REJECTED,
                code="PROVIDER_TEMPORARILY_UNAVAILABLE",
                rejection_disposition=RejectionDisposition.RETRYABLE,
            )
        )
        record = self.coordinator.dispatch(
            rtt_id=self.rtt_id,
            adapter=adapter,
            at=self.now + timedelta(seconds=22),
        )

        self.assertEqual(record.state, ProviderSubmissionState.REJECTED)
        self.assertEqual(record.rejection_disposition, RejectionDisposition.RETRYABLE)

    def test_every_operation_event_is_ed25519_signed_and_omits_account_refs(self) -> None:
        self.coordinator.dispatch(
            rtt_id=self.rtt_id,
            adapter=FakeProviderAdapter(),
            at=self.now + timedelta(seconds=22),
        )
        events = self.operations.pending_outbox(limit=100)

        self.assertEqual(len(events), 3)
        for event in events:
            self.assertTrue(
                self.signatures.verify_artifact(
                    event.signed_event,
                    expected_artifact_type=ArtifactType.EXECUTION_EVENT,
                ).valid
            )
            serialized = repr(event.signed_event.to_dict())
            self.assertNotIn("PAYER-SECRET-REF", serialized)
            self.assertNotIn("BENEFICIARY-SECRET-REF", serialized)

    def test_outbox_relay_claims_and_publishes_signed_events(self) -> None:
        self.coordinator.dispatch(
            rtt_id=self.rtt_id,
            adapter=FakeProviderAdapter(),
            at=self.now + timedelta(seconds=22),
        )
        publisher = FakeEventPublisher()
        outcomes = OutboxRelay(
            operations=self.operations,
            worker_id="outbox-worker-01",
        ).publish_batch(
            publisher=publisher,
            at=self.now + timedelta(seconds=23),
        )

        self.assertEqual(len(publisher.events), 3)
        self.assertTrue(
            all(row.delivery_state is OutboxDeliveryState.PUBLISHED for row in outcomes)
        )
        self.assertEqual(self.operations.pending_outbox(), ())

    def test_outbox_failure_is_rescheduled_with_a_lease_safe_retry(self) -> None:
        self.coordinator.prepare(
            rtt_id=self.rtt_id, at=self.now + timedelta(seconds=22)
        )
        relay = OutboxRelay(
            operations=self.operations,
            worker_id="outbox-worker-01",
            max_attempts=3,
        )
        outcomes = relay.publish_batch(
            publisher=FakeEventPublisher(fail=True),
            at=self.now + timedelta(seconds=23),
        )

        self.assertEqual(outcomes[0].delivery_state, OutboxDeliveryState.PENDING)
        self.assertEqual(outcomes[0].last_error, "ConnectionError")
        self.assertIsNone(outcomes[0].lease_owner)


if __name__ == "__main__":
    unittest.main()
