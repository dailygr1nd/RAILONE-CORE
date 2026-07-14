"""Destructive opt-in PostgreSQL integration test.

Run only against a disposable database:

    RAILONE_TEST_DATABASE_URL=postgresql://... \
    RAILONE_ALLOW_TEST_SCHEMA_RESET=1 python run_tests.py
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from railone_authority import ExecutionAuthorityService
from railone_contracts import (
    ActorReference,
    ContextType,
    OriginContext,
    PaymentPurpose,
    QuoteAcceptanceCommand,
    QuoteAcceptanceService,
    QuoteService,
    QuoteTerms,
)
from railone_crypto.key_provider import InMemoryEd25519KeyProvider, KeyPurpose
from railone_crypto.signature_service import SignatureService
from railone_execution import (
    ExecutionPlanningService,
    LinkStatus,
    RouteCandidate,
    RttAttemptService,
)
from railone_operations import (
    ProviderOutcome,
    ProviderSubmissionCoordinator,
    ProviderSubmissionResult,
)
from railone_postgres import (
    MigrationRunner,
    PostgresContractStore,
    PostgresDatabase,
    PostgresExecutionStore,
    PostgresOperationsStore,
    PostgresProviderOutcomeProjectionStore,
    psycopg_connection_factory,
)
from railone_projection import ProviderProgressState, SignedProviderOutcomeProjector


_DSN = os.environ.get("RAILONE_TEST_DATABASE_URL", "")
_RESET_ALLOWED = os.environ.get("RAILONE_ALLOW_TEST_SCHEMA_RESET") == "1"
_LIVE_REQUIRED = os.environ.get("RAILONE_REQUIRE_LIVE_POSTGRES") == "1"


class AcceptedAdapter:
    provider_id = "MPESA-KE"
    supports_idempotency = True

    def submit(self, request):
        return ProviderSubmissionResult(
            outcome=ProviderOutcome.ACCEPTED,
            code="ACCEPTED_FOR_PROCESSING",
            external_reference="MPESA-SANDBOX-001",
        )


@unittest.skipUnless(
    _DSN and _RESET_ALLOWED,
    "requires disposable RAILONE_TEST_DATABASE_URL and explicit schema-reset opt-in",
)
class LivePostgresRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.factory = psycopg_connection_factory(_DSN)
        try:
            connection = cls.factory()
        except Exception as exc:
            if _LIVE_REQUIRED:
                raise
            raise unittest.SkipTest(
                "PostgreSQL integration unavailable; provide a real disposable "
                "database DSN or set RAILONE_REQUIRE_LIVE_POSTGRES=1 to make "
                f"this a hard gate ({type(exc).__name__})"
            ) from None
        try:
            with connection.cursor() as cursor:
                cursor.execute("DROP SCHEMA IF EXISTS railone CASCADE")
            connection.commit()
        finally:
            connection.close()
        cls.migrations = Path(__file__).resolve().parents[1] / "migrations"
        MigrationRunner(
            connection_factory=cls.factory,
            migrations_directory=cls.migrations,
        ).apply_all()

    def test_migrations_are_checksum_idempotent(self):
        results = MigrationRunner(
            connection_factory=self.factory,
            migrations_directory=self.migrations,
        ).apply_all()
        self.assertTrue(all(result.already_applied for result in results))

    def test_contract_execution_submission_and_projection_round_trip(self):
        now = datetime(2026, 7, 14, 19, 0, tzinfo=timezone.utc)
        keys = InMemoryEd25519KeyProvider()
        keys.generate(
            key_id="R1CORE:quote:live", owner_id="R1CORE",
            purpose=KeyPurpose.QUOTE_SIGNING,
            not_before=now - timedelta(days=1), not_after=now + timedelta(days=30),
        )
        keys.generate(
            key_id="R1CORE:execution:live", owner_id="R1CORE",
            purpose=KeyPurpose.EXECUTION_SIGNING,
            not_before=now - timedelta(days=1), not_after=now + timedelta(days=30),
        )
        signatures = SignatureService(keys)
        database = PostgresDatabase(self.factory)
        contracts = PostgresContractStore(database)
        executions = PostgresExecutionStore(database)
        operations = PostgresOperationsStore(database)

        quote = QuoteService(signatures).issue_quote(
            terms=QuoteTerms(
                request_id="REQ-LIVE-001",
                payer=ActorReference("MERCHANT", "MER002", "PAYER-REF"),
                beneficiary=ActorReference("SUPPLIER", "SUP001", "PAYEE-REF"),
                purpose=PaymentPurpose.SUPPLIER_PAYMENT,
                amount_minor=10_000, currency_from="KES",
                receive_amount_minor=9_950, currency_to="KES",
                total_fee_minor=50, routing_budget_minor=100, fx_rate="1.000000",
                corridor_id="KE-DOMESTIC", service_level="STANDARD",
                routing_policy_id="POLICY-KE-PILOT", pricing_version="2026-07",
            ),
            signing_key_id="R1CORE:quote:live", issued_at=now,
            expires_at=now + timedelta(minutes=5),
        )
        contract = QuoteAcceptanceService(
            signatures=signatures,
            authority=ExecutionAuthorityService(signatures),
            store=contracts,
            utt_signing_key_id="R1CORE:execution:live",
            authority_signing_key_id="R1CORE:execution:live",
        ).accept(
            QuoteAcceptanceCommand(
                signed_quote=quote,
                origin=OriginContext(
                    origin_system="AVIA", origin_intent_id="AVIA-LIVE-001",
                    context_type=ContextType.MERCHANT,
                    purpose=PaymentPurpose.SUPPLIER_PAYMENT,
                    merchant_id="MER002", branch_id="BR001",
                ),
                authorization_method="MERCHANT_ACTOR_ATTESTATION",
                authorization_reference="AUTH-LIVE-001",
                idempotency_key="IDEM-LIVE-001",
            ),
            at=now + timedelta(seconds=1),
        ).contract
        route = RouteCandidate(
            route_id="MPESA", source_institution_id="BANK-001",
            destination_institution_id="MNO-001", rail="MOBILE_MONEY",
            provider="MPESA-KE", adapter="mpesa-sandbox-v1",
            currency_from="KES", currency_to="KES", min_amount_minor=100,
            max_amount_minor=1_000_000, latency_ms=500, congestion_bps=100,
            liquidity_capacity_minor=5_000_000, throughput_headroom_bps=9000,
            speed_bps=8500, estimated_cost_minor=30, link_status=LinkStatus.UP,
            telemetry_observed_at=now, telemetry_expires_at=now + timedelta(minutes=5),
        )
        ExecutionPlanningService(
            signatures=signatures, contracts=contracts, executions=executions
        ).build_plan(utt_id=contract.utt_id, candidates=(route,), at=now + timedelta(seconds=2))
        attempt = RttAttemptService(
            signatures=signatures, contracts=contracts, executions=executions,
            rtt_signing_key_id="R1CORE:execution:live",
        ).start_next(utt_id=contract.utt_id, at=now + timedelta(seconds=3))
        submission = ProviderSubmissionCoordinator(
            signatures=signatures, contracts=contracts, executions=executions,
            operations=operations,
            event_signing_key_id="R1CORE:execution:live",
        ).dispatch(rtt_id=attempt.rtt_id, adapter=AcceptedAdapter(), at=now + timedelta(seconds=4))

        outcome_store = PostgresProviderOutcomeProjectionStore(database)
        projector = SignedProviderOutcomeProjector(signatures=signatures, store=outcome_store)
        for event in operations.pending_outbox(limit=100):
            projector.project(event.signed_event, at=now + timedelta(seconds=5))
        projected = outcome_store.get(submission.submission_id)
        self.assertEqual(projected.state, ProviderProgressState.ACCEPTED_FOR_PROCESSING)
        self.assertEqual(projected.submission_version, 3)


if __name__ == "__main__":
    unittest.main()
