from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from railone_authority import ExecutionAuthorityService
from railone_contracts import (
    AccountRole, ActorReference, ContextType, InMemoryContractStore,
    OriginContext, PaymentPurpose, QuoteAcceptanceCommand, QuoteAcceptanceService,
    QuoteTerms,
)
from railone_crypto.key_provider import InMemoryEd25519KeyProvider, KeyPurpose
from railone_crypto.signature_service import ArtifactType, SignatureService
from railone_execution import (
    ExecutionPlanningService, InMemoryExecutionStore, LinkStatus, RouteCandidate,
    RttAttemptService,
)
from railone_notifications import (
    InMemorySettlementNotificationStore, SettlementNotificationService,
    SmsDeliveryState, SmsGatewayResult, SmsOutboxRelay,
)
from tests.support import endpoint, quote_service


class Contacts:
    def __init__(self) -> None:
        self.calls = 0

    def resolve_sms_destination(self, contact_binding_id: str) -> str:
        self.calls += 1
        return "+254700000001"


class Gateway:
    supports_idempotency = False

    def __init__(self, *, raises: bool = False) -> None:
        self.raises = raises
        self.calls = 0

    def send(self, *, idempotency_key, destination, body):
        self.calls += 1
        if self.raises:
            raise TimeoutError("unknown SMS gateway outcome")
        return SmsGatewayResult(True, "ACCEPTED", "SMS-GW-001")


class SettlementNotificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 7, 14, 16, 5, tzinfo=timezone.utc)
        keys = InMemoryEd25519KeyProvider()
        for key_id, purpose in (
            ("quote", KeyPurpose.QUOTE_SIGNING),
            ("execution", KeyPurpose.EXECUTION_SIGNING),
            ("settlement", KeyPurpose.SETTLEMENT_SIGNING),
        ):
            keys.generate(
                key_id=key_id, owner_id="R1CORE", purpose=purpose,
                not_before=self.now - timedelta(days=1),
                not_after=self.now + timedelta(days=30),
            )
        self.signatures = SignatureService(keys)
        self.contracts = InMemoryContractStore()
        self.executions = InMemoryExecutionStore(self.contracts)
        quote = quote_service(self.signatures).issue_quote(
            terms=QuoteTerms(
                request_id="REQ-NOTIFY-001",
                payer=ActorReference(
                    "PERSON", "CUID-SENDER",
                    endpoint(
                        "BIND-SENDER", AccountRole.DEBIT,
                        contact_binding_id="CONTACT-SENDER",
                    ),
                    "Noel",
                ),
                beneficiary=ActorReference(
                    "PERSON", "CUID-RECEIVER",
                    endpoint(
                        "BIND-RECEIVER", AccountRole.CREDIT,
                        display_hint="****5678", contact_binding_id="CONTACT-RECEIVER",
                    ),
                    "Amina",
                ),
                purpose=PaymentPurpose.PERSON_TO_PERSON,
                amount_minor=250_000, currency_from="KES",
                receive_amount_minor=250_000, currency_to="KES",
                total_fee_minor=2_500, routing_budget_minor=1_000,
                fx_rate="1.000000", corridor_id="KE-DOMESTIC",
                service_level="STANDARD", routing_policy_id="POLICY-KE",
                pricing_version="2026-07",
            ),
            signing_key_id="quote", issued_at=self.now,
            expires_at=self.now + timedelta(minutes=1),
        )
        contract = QuoteAcceptanceService(
            signatures=self.signatures,
            authority=ExecutionAuthorityService(self.signatures),
            store=self.contracts, utt_signing_key_id="execution",
            authority_signing_key_id="execution",
        ).accept(
            QuoteAcceptanceCommand(
                signed_quote=quote,
                origin=OriginContext(
                    origin_system="RAILONE_CLIENT", origin_intent_id="P2P-001",
                    context_type=ContextType.P2P,
                    purpose=PaymentPurpose.PERSON_TO_PERSON,
                    continuity_uid="CUID-SENDER",
                ),
                authorization_method="IDENTITY_SESSION_ATTESTATION",
                authorization_reference="AUTH-001", idempotency_key="IDEM-001",
            ),
            at=self.now + timedelta(seconds=1),
        ).contract
        route = RouteCandidate(
            route_id="MPESA", source_institution_id="INST-SOURCE",
            destination_institution_id="INST-DEST", rail="MOBILE_MONEY",
            provider="MPESA-KE", adapter="mpesa-v3", currency_from="KES",
            currency_to="KES", min_amount_minor=100, max_amount_minor=1_000_000,
            latency_ms=100, congestion_bps=100, liquidity_capacity_minor=2_000_000,
            throughput_headroom_bps=9000, speed_bps=9000,
            estimated_cost_minor=100, link_status=LinkStatus.UP,
            telemetry_observed_at=self.now,
            telemetry_expires_at=self.now + timedelta(minutes=5),
        )
        ExecutionPlanningService(
            signatures=self.signatures, contracts=self.contracts,
            executions=self.executions,
        ).build_plan(
            utt_id=contract.utt_id, candidates=(route,),
            at=self.now + timedelta(seconds=2),
        )
        self.attempts = RttAttemptService(
            signatures=self.signatures, contracts=self.contracts,
            executions=self.executions, rtt_signing_key_id="execution",
            allow_unverified_endpoints_for_tests=True,
        )
        self.attempt = self.attempts.start_next(
            utt_id=contract.utt_id, at=self.now + timedelta(seconds=3)
        )
        self.utt_id = contract.utt_id
        self.store = InMemorySettlementNotificationStore()
        self.service = SettlementNotificationService(
            signatures=self.signatures, contracts=self.contracts,
            executions=self.executions, store=self.store,
            settlement_signing_key_id="settlement",
        )

    def test_notification_cannot_be_created_before_external_finality(self) -> None:
        with self.assertRaises(PermissionError):
            self.service.confirm_provider_settlement(
                utt_id=self.utt_id, provider_id="MPESA-KE",
                provider_transaction_id="TXN-001",
                callback_event_id="MPESA-RESULT-001", at=self.now,
            )
        self.assertEqual(self.store.pending_notifications(), ())

    def _settle(self):
        self.attempts.record_success(
            rtt_id=self.attempt.rtt_id, actual_cost_minor=0,
            at=self.now + timedelta(seconds=4),
        )
        return self.service.confirm_provider_settlement(
            utt_id=self.utt_id, provider_id="MPESA-KE",
            provider_transaction_id="TXN-001",
            callback_event_id="MPESA-RESULT-001",
            at=self.now + timedelta(seconds=5),
        )

    def test_verified_settlement_creates_signed_sender_and_receiver_sms_once(self) -> None:
        first = self._settle()
        second = self.service.confirm_provider_settlement(
            utt_id=self.utt_id, provider_id="MPESA-KE",
            provider_transaction_id="TXN-001",
            callback_event_id="MPESA-RESULT-001",
            at=self.now + timedelta(minutes=1),
        )
        self.assertFalse(first.replayed)
        self.assertTrue(second.replayed)
        self.assertEqual(len(first.notifications), 2)
        self.assertTrue(self.signatures.verify_artifact(
            first.evidence.signed_evidence,
            expected_artifact_type=ArtifactType.SETTLEMENT_EVIDENCE,
        ).valid)
        bodies = " ".join(item.rendered_body for item in first.notifications)
        self.assertIn("RailOne: SETTLED.", bodies)
        self.assertIn("KES 2,500.00", bodies)
        self.assertIn("Amina", bodies)
        self.assertNotIn("CUID-", bodies)
        self.assertNotIn("CONTACT-", bodies)
        self.assertNotIn("BIND-", bodies)

    def test_unknown_sms_gateway_outcome_is_not_automatically_resent(self) -> None:
        result = self._settle()
        notification = result.notifications[0]
        gateway = Gateway(raises=True)
        contacts = Contacts()
        relay = SmsOutboxRelay(store=self.store)
        first = relay.deliver(
            notification_id=notification.notification_id,
            contacts=contacts, gateway=gateway, at=self.now + timedelta(seconds=6),
        )
        second = relay.deliver(
            notification_id=notification.notification_id,
            contacts=contacts, gateway=gateway, at=self.now + timedelta(seconds=7),
        )
        self.assertEqual(first.state, SmsDeliveryState.UNKNOWN)
        self.assertEqual(second.state, SmsDeliveryState.UNKNOWN)
        self.assertEqual(gateway.calls, 1)


if __name__ == "__main__":
    unittest.main()
