from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from railone_authority import ExecutionAuthorityService
from railone_contracts import (
    AccountRole,
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
    InMemoryAccountEndpointResolver,
    InMemoryOperationsStore,
    OutboxDeliveryState,
    OutboxRelay,
    ProviderOutcome,
    ProviderSubmissionCoordinator,
    ProviderSubmissionResult,
    ProviderSubmissionState,
    RejectionDisposition,
)
from tests.support import endpoint, quote_service


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
            owner_id=getattr(self, "core_owner_id", "R1CORE"),
            purpose=KeyPurpose.QUOTE_SIGNING,
            not_before=self.now - timedelta(days=1),
            not_after=self.now + timedelta(days=90),
        )
        keys.generate(
            key_id="R1CORE:execution:2026-01",
            owner_id=getattr(self, "core_owner_id", "R1CORE"),
            purpose=KeyPurpose.EXECUTION_SIGNING,
            not_before=self.now - timedelta(days=1),
            not_after=self.now + timedelta(days=90),
        )
        self.signatures = SignatureService(keys)
        self.keys = keys  # Synthetic institutional keys for the strict v3 fixture.
        self.contracts = InMemoryContractStore()
        self.executions = InMemoryExecutionStore(self.contracts)
        self.operations = InMemoryOperationsStore()
        self.endpoint_resolver = InMemoryAccountEndpointResolver()
        self.endpoint_resolver.register(
            institution_id="INST-SOURCE", account_binding_id="BIND-PAYER-OPS",
            provider_reference="PAYER-SECRET-REF",
        )
        self.endpoint_resolver.register(
            institution_id="INST-DEST", account_binding_id="BIND-BEN-OPS",
            provider_reference="BENEFICIARY-SECRET-REF",
        )
        self.rtt_id = self._create_current_rtt()
        self.coordinator = ProviderSubmissionCoordinator(
            signatures=self.signatures,
            contracts=self.contracts,
            executions=self.executions,
            operations=self.operations,
            endpoint_resolver=self.endpoint_resolver,
            event_signing_key_id="R1CORE:execution:2026-01",
        )

    def _create_current_rtt(self, *, institutional=False, sender_first=False) -> str:
        if sender_first and not institutional:
            raise ValueError("sender_first fixture requires institutional P2P")
        payer_id = "CUID-" + "A" * 32 if institutional else "MER002"
        beneficiary_id = "CUID-" + "B" * 32 if institutional else "SUP001"
        purpose = PaymentPurpose.PERSON_TO_PERSON if institutional else PaymentPurpose.SUPPLIER_PAYMENT
        origin = (
            OriginContext(
                origin_system="RAILONE", origin_intent_id="P2P-OPS-001",
                context_type=ContextType.P2P, purpose=purpose, continuity_uid=payer_id,
            )
            if institutional else
            OriginContext(
                origin_system="AVIA", origin_intent_id="AVIA-SUPPLIER-OPS-001",
                context_type=ContextType.MERCHANT, purpose=purpose,
                merchant_id=payer_id, branch_id="BR001",
            )
        )
        quote = quote_service(self.signatures).issue_quote(
            terms=QuoteTerms(
                request_id="REQ-OPS-001",
                payer=ActorReference(
                    "PERSON" if institutional else "MERCHANT", payer_id,
                    endpoint("acctbind_payer_ops" if institutional else "BIND-PAYER-OPS", AccountRole.DEBIT),
                ),
                beneficiary=ActorReference(
                    "PERSON" if institutional else "SUPPLIER", beneficiary_id,
                    endpoint("acctbind_ben_ops" if institutional else "BIND-BEN-OPS", AccountRole.CREDIT),
                ),
                purpose=purpose,
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
        # Strict institutional fixtures exercise the real externally signed
        # sender-first v3 protocol; ordinary merchant fixtures keep the v0.16
        # acceptance semantics they were originally written to test.
        sender_authority = receiver_authority = None
        if sender_first:
            from railone_authority.bilateral import BilateralAuthorityService
            for key_id, owner_id in (
                ("fixture-payer-v3", payer_id),
                ("fixture-receiver-v3", beneficiary_id),
            ):
                self.keys.generate(
                    key_id=key_id, owner_id=owner_id,
                    purpose=KeyPurpose.EXECUTION_SIGNING,
                    not_before=self.now - timedelta(days=1),
                    not_after=self.now + timedelta(days=2),
                )
            bilateral = BilateralAuthorityService(self.signatures)
            sender_authority = bilateral.issue_sender_authority(
                signed_quote=quote, signing_key_id="fixture-payer-v3",
                authorized_at=self.now + timedelta(seconds=5),
                expires_at=self.now + timedelta(minutes=2),
            )
            receiver_authority = bilateral.issue_receiver_acceptance(
                signed_quote=quote, sender=sender_authority,
                signing_key_id="fixture-receiver-v3",
                accepted_at=self.now + timedelta(seconds=7),
                expires_at=self.now + timedelta(minutes=2),
            )
        contract = QuoteAcceptanceService(
            signatures=self.signatures,
            authority=ExecutionAuthorityService(self.signatures),
            store=self.contracts,
            utt_signing_key_id="R1CORE:execution:2026-01",
            authority_signing_key_id="R1CORE:execution:2026-01",
            require_bilateral_p2p=sender_first,
        ).accept(
            QuoteAcceptanceCommand(
                signed_quote=quote,
                origin=origin,
                authorization_method="MERCHANT_ACTOR_ATTESTATION",
                authorization_reference="AUTH-OPS-001",
                idempotency_key="IDEM-OPS-001",
                sender_authority=sender_authority,
                receiver_authority=receiver_authority,
            ),
            at=self.now + timedelta(seconds=10),
        ).contract
        route = RouteCandidate(
            route_id="FAST",
            source_institution_id="INST-SOURCE",
            destination_institution_id="INST-DEST",
            rail="MOBILE_MONEY",
            provider="PROVIDER-FAST",
            adapter="provider-fast@1.0.0" if institutional else "provider-fast-v1",
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
            allow_unverified_endpoints_for_tests=True,
        ).start_next(
            utt_id=contract.utt_id,
            at=self.now + timedelta(seconds=21),
        )
        return attempt.rtt_id

    def test_sender_first_institutional_fixture_persists_bilateral_before_rtt(self) -> None:
        """Guard the exact synthetic fixture used by live dispatch tests."""
        from functools import partial
        from railone_authority.bilateral import BilateralAuthorityService

        fixture = ProviderOperationsTests(
            "test_preparation_is_idempotent_and_uses_stable_provider_key"
        )
        fixture._create_current_rtt = partial(
            fixture._create_current_rtt, institutional=True, sender_first=True,
        )
        fixture.setUp()
        attempt = fixture.executions.require_attempt(fixture.rtt_id)
        utt = fixture.contracts.require_utt(attempt.utt_id)
        sender, receiver = fixture.contracts.require_bilateral_authorities(attempt.utt_id)
        self.assertEqual(utt.payload["authority_version"], 3)
        self.assertLess(sender.protected["iat"], receiver.protected["iat"])
        self.assertEqual(
            receiver.payload["etk_s_digest"], sender.protected["payload_sha256"],
        )
        BilateralAuthorityService(fixture.signatures).verify_utt(
            signed_utt=utt, sender=sender, receiver=receiver,
            at=fixture.now + timedelta(seconds=22),
        )

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
