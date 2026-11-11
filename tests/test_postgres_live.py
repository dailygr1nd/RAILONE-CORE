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
    AccountRole,
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
    InMemoryAccountEndpointResolver,
    ProviderOutcome,
    ProviderSubmissionCoordinator,
    ProviderSubmissionResult,
)
from tests.support import endpoint, quote_service
from railone_postgres import (
    MigrationRunner,
    PostgresContractStore,
    PostgresDatabase,
    PostgresExecutionStore,
    PostgresOperationsStore,
    PostgresProviderOutcomeProjectionStore,
    psycopg_connection_factory,
    PostgresApiAuditStore,
    PostgresRateLimitStore,
    PostgresTokenRevocationStore,
)
from railone_projection import ProviderProgressState, SignedProviderOutcomeProjector


_DSN = os.environ.get("RAILONE_TEST_DATABASE_URL", "")
_RESET_ALLOWED = os.environ.get("RAILONE_ALLOW_TEST_SCHEMA_RESET") == "1"
_LIVE_REQUIRED = os.environ.get("RAILONE_REQUIRE_LIVE_POSTGRES") == "1"


def _attempt_reserve(action) -> str:
    from railone_postgres import EconomicFenceViolation
    try:
        action()
        return "RESERVED"
    except EconomicFenceViolation:
        return "DENIED"


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
        cls.factory = staticmethod(psycopg_connection_factory(_DSN))
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
                cursor.execute("DROP SCHEMA IF EXISTS railone_bank CASCADE")
                cursor.execute("DROP SCHEMA IF EXISTS railone CASCADE")
            connection.commit()
        finally:
            connection.close()
        cls.migrations = Path(__file__).resolve().parents[1] / "migrations"
        MigrationRunner(
            connection_factory=cls.factory,
            migrations_directory=cls.migrations,
        ).apply_all()

    def test_institutional_dispatch_reserves_before_adapter_and_blocks_replay(self):
        self.setUpClass()
        from tests.institutional_live_support import exercise_institutional_dispatch
        exercise_institutional_dispatch(self, PostgresDatabase(self.factory))

    def test_institutional_timeout_retains_hold_and_blocks_replay(self):
        self.setUpClass()
        from tests.institutional_live_support import exercise_institutional_dispatch
        exercise_institutional_dispatch(self, PostgresDatabase(self.factory), scenario="timeout")

    def test_institutional_crash_retains_hold_and_blocks_replay(self):
        self.setUpClass()
        from tests.institutional_live_support import exercise_institutional_dispatch
        exercise_institutional_dispatch(self, PostgresDatabase(self.factory), scenario="crash")

    def test_migrations_are_checksum_idempotent(self):
        results = MigrationRunner(
            connection_factory=self.factory,
            migrations_directory=self.migrations,
        ).apply_all()
        self.assertTrue(all(result.already_applied for result in results))
        self.assertIn("0015", {result.version for result in results})
        connection = self.factory()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT to_regclass('railone.institution_dispatch_wrappers') AS relation")
                self.assertIsNotNone(cursor.fetchone()["relation"])
                cursor.execute("""SELECT COUNT(*) AS count FROM pg_trigger
                               WHERE tgrelid = 'railone.institution_dispatch_wrappers'::regclass
                                 AND tgname = 'institution_dispatch_wrappers_append_only'""")
                self.assertEqual(cursor.fetchone()["count"], 1)
        finally:
            connection.close()

    def test_sensitive_vault_schema_removes_plaintext_fingerprint(self):
        from railone_postgres import PostgresEncryptedSecretStore
        from railone_security import EncryptedAccountEndpointVault
        from tests.test_envelope_encryption import encryption_fixture

        database = PostgresDatabase(self.factory)
        with database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute("""SELECT COUNT(*) AS n FROM information_schema.columns
                           WHERE table_schema='railone' AND table_name='encrypted_secrets'
                             AND column_name='plaintext_sha256'""")
            self.assertEqual(cursor.fetchone()["n"], 0)
        _, _, encryption = encryption_fixture()
        store = PostgresEncryptedSecretStore(database)
        vault = EncryptedAccountEndpointVault(encryption=encryption, store=store)
        vault.register(institution_id="SYNTHETIC-INST", account_binding_id="SYNTHETIC-BIND",
                       provider_reference="SYNTHETIC-ENDPOINT")
        self.assertEqual(vault.resolve(institution_id="SYNTHETIC-INST",
                                       account_binding_id="SYNTHETIC-BIND"), "SYNTHETIC-ENDPOINT")

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

        quote = quote_service(signatures).issue_quote(
            terms=QuoteTerms(
                request_id="REQ-LIVE-001",
                payer=ActorReference(
                    "MERCHANT", "MER002",
                    endpoint("BIND-LIVE-PAYER", AccountRole.DEBIT, institution_id="BANK-001"),
                ),
                beneficiary=ActorReference(
                    "SUPPLIER", "SUP001",
                    endpoint("BIND-LIVE-PAYEE", AccountRole.CREDIT, institution_id="MNO-001"),
                ),
                purpose=PaymentPurpose.SUPPLIER_PAYMENT,
                amount_minor=10_000, currency_from="KES",
                receive_amount_minor=9_950, currency_to="KES",
                total_fee_minor=50, routing_budget_minor=50, fx_rate="1.000000",
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
        plan = ExecutionPlanningService(
            signatures=signatures, contracts=contracts, executions=executions
        ).build_plan(utt_id=contract.utt_id, candidates=(route,), at=now + timedelta(seconds=2))
        decision = executions.require_decision_for_plan(plan.plan_id)
        decision.verify(plan=plan)
        with database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) AS count FROM railone.route_decision_records WHERE plan_id=%s",
                (plan.plan_id,),
            )
            self.assertEqual(cursor.fetchone()["count"], 1)
        attempt = RttAttemptService(
            signatures=signatures, contracts=contracts, executions=executions,
            rtt_signing_key_id="R1CORE:execution:live",
            allow_unverified_endpoints_for_tests=True,
        ).start_next(utt_id=contract.utt_id, at=now + timedelta(seconds=3))
        endpoint_resolver = InMemoryAccountEndpointResolver()
        endpoint_resolver.register(
            institution_id="BANK-001", account_binding_id="BIND-LIVE-PAYER",
            provider_reference="PAYER-REF",
        )
        endpoint_resolver.register(
            institution_id="MNO-001", account_binding_id="BIND-LIVE-PAYEE",
            provider_reference="PAYEE-REF",
        )
        from railone_postgres import PostgresEconomicEffectFence, EconomicFenceViolation
        from railone_crypto.signature_service import ArtifactType
        keys.generate(
            key_id="R1CORE:no-effect:live-test", owner_id="R1CORE",
            purpose=KeyPurpose.SETTLEMENT_SIGNING,
            not_before=now - timedelta(days=1), not_after=now + timedelta(days=30),
        )
        coordinator = ProviderSubmissionCoordinator(
            signatures=signatures, contracts=contracts, executions=executions,
            operations=operations, endpoint_resolver=endpoint_resolver,
            event_signing_key_id="R1CORE:execution:live",
        )
        prepared, request = coordinator.prepare(rtt_id=attempt.rtt_id, at=now + timedelta(seconds=4))
        fence = PostgresEconomicEffectFence(
            database, signatures=signatures,
            trusted_no_effect_signing_keys=frozenset({"R1CORE:no-effect:live-test"}),
        )
        fence.assert_dispatch_safe(
            utt_id=contract.utt_id, rtt_id=attempt.rtt_id, fence_epoch=1,
            release_evidence_ref=None, at=now + timedelta(seconds=4),
        )
        # Two workers racing the same UTT must create ONE durable reservation.
        from concurrent.futures import ThreadPoolExecutor
        def reserve_once():
            return fence.reserve_dispatch(
                utt_id=contract.utt_id, rtt_id=attempt.rtt_id, fence_epoch=1,
                release_evidence_ref=None, request_sha256=request.request_sha256,
                at=now + timedelta(seconds=4),
            )
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: _attempt_reserve(reserve_once), range(2)))
        self.assertEqual(results.count("RESERVED"), 1)
        self.assertEqual(results.count("DENIED"), 1)
        with self.assertRaises(EconomicFenceViolation):
            reserve_once()
        submission = coordinator.dispatch(
            rtt_id=attempt.rtt_id, adapter=AcceptedAdapter(), at=now + timedelta(seconds=4)
        )
        fence.record_provider_outcome(
            utt_id=contract.utt_id, rtt_id=attempt.rtt_id,
            outcome="ACCEPTED", at=now + timedelta(seconds=5),
        )
        with self.assertRaises(EconomicFenceViolation):
            fence.assert_dispatch_safe(
                utt_id=contract.utt_id, rtt_id=attempt.rtt_id,
                fence_epoch=1, release_evidence_ref=None,
                at=now + timedelta(seconds=5),
            )
        # Synthetic no-effect assertion tests transition mechanics only; the
        # real signer must first verify actual authenticated provider evidence.
        evidence = signatures.sign_artifact(
            artifact_type=ArtifactType.NO_EFFECT_EVIDENCE,
            key_id="R1CORE:no-effect:live-test", issued_at=now + timedelta(seconds=6),
            payload={
                "evidence_id":"EVID-DISPOSABLE-001", "utt_id":contract.utt_id,
                "rtt_id":attempt.rtt_id, "provider_id":"MPESA-KE",
                "finding":"NO_ECONOMIC_EFFECT", "source_evidence_digest":"f" * 64,
                "observed_at_epoch":int((now + timedelta(seconds=6)).timestamp()),
            },
        )
        self.assertEqual(fence.release_verified_no_effect(
            evidence=evidence, at=now + timedelta(seconds=7)), 2)
        with database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT state,fence_epoch,last_release_evidence_id "
                "FROM railone.utt_economic_fences WHERE utt_id=%s", (contract.utt_id,)
            )
            hold = cursor.fetchone()
            self.assertEqual(hold["state"], "OPEN")
            self.assertEqual(hold["fence_epoch"], 2)
            self.assertEqual(hold["last_release_evidence_id"], "EVID-DISPOSABLE-001")

        outcome_store = PostgresProviderOutcomeProjectionStore(database)
        projector = SignedProviderOutcomeProjector(signatures=signatures, store=outcome_store)
        for event in operations.pending_outbox(limit=100):
            projector.project(event.signed_event, at=now + timedelta(seconds=5))
        projected = outcome_store.get(submission.submission_id)
        self.assertEqual(projected.state, ProviderProgressState.ACCEPTED_FOR_PROCESSING)
        self.assertEqual(projected.submission_version, 3)

    def test_bank_analytics_schema_is_allowlisted_and_private(self):
        from railone_postgres import BankMetric, PostgresBankMetricsPublisher
        from datetime import timedelta
        database = PostgresDatabase(self.factory)
        with database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('railone_bank.metrics') AS relation")
            self.assertIsNotNone(cursor.fetchone()["relation"])
            cursor.execute("""SELECT relrowsecurity,relforcerowsecurity
                           FROM pg_class WHERE oid='railone.bank_analytics_publications'::regclass""")
            row = cursor.fetchone()
            self.assertTrue(row["relrowsecurity"])
            self.assertTrue(row["relforcerowsecurity"])
            cursor.execute("SELECT COUNT(*) AS n FROM railone.bank_analytics_publications")
            self.assertEqual(cursor.fetchone()["n"], 0)
        # Unmapped login (and even the privileged migration login) is not
        # mapped to a bank by the public view. RLS and view scope both fail closed.
        with database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS n FROM railone_bank.metrics")
            self.assertEqual(cursor.fetchone()["n"], 0)

    def test_bank_metrics_are_isolated_for_distinct_database_logins(self):
        """Live RLS/view access gate: two real DB logins must never cross-read."""
        from uuid import uuid4
        from secrets import token_urlsafe
        from psycopg import sql
        from psycopg.conninfo import make_conninfo
        from railone_postgres import BankMetric, PostgresBankMetricsPublisher, PostgresBankMetricsReader

        token = uuid4().hex[:12]
        read_role = "r1bank_read_" + token
        a_login = "r1bank_a_" + token
        b_login = "r1bank_b_" + token
        a_id = "BANK-TEST-A-" + token.upper()
        b_id = "BANK-TEST-B-" + token.upper()
        password_a, password_b = token_urlsafe(24), token_urlsafe(24)
        database = PostgresDatabase(self.factory)
        try:
            with database.transaction() as connection, connection.cursor() as cursor:
                cursor.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(read_role)))
                for name, password in ((a_login, password_a), (b_login, password_b)):
                    cursor.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                        sql.Identifier(name), sql.Literal(password)))
                    cursor.execute(sql.SQL("GRANT {} TO {}").format(
                        sql.Identifier(read_role), sql.Identifier(name)))
                cursor.execute(sql.SQL("GRANT USAGE ON SCHEMA railone_bank TO {}").format(
                    sql.Identifier(read_role)))
                cursor.execute(sql.SQL("GRANT EXECUTE ON FUNCTION railone_bank.current_institution_id() TO {}").format(
                    sql.Identifier(read_role)))
                cursor.execute(sql.SQL("GRANT SELECT ON railone_bank.metrics TO {}").format(
                    sql.Identifier(read_role)))
                for bank_id, login in ((a_id, a_login), (b_id, b_login)):
                    cursor.execute(
                        """INSERT INTO railone.partner_institutions
                           (institution_id,display_name,country_codes,currencies,
                            supported_roles,status,created_at,updated_at)
                           VALUES (%s,%s,%s,%s,%s,'ACTIVE',now(),now())""",
                        (bank_id, bank_id, ["TZ"], ["TZS"], ["SOURCE","DESTINATION"]),
                    )
                    cursor.execute(
                        """INSERT INTO railone.bank_analytics_principals
                           (login_role,institution_id,enabled) VALUES (%s,%s,true)""",
                        (login, bank_id),
                    )
            metric = BankMetric("OWN_UTT_SETTLED_TOTAL",
                                datetime(2026, 11, 1, tzinfo=timezone.utc),
                                datetime(2026, 11, 2, tzinfo=timezone.utc),
                                25, 50)
            publisher = PostgresBankMetricsPublisher(database)
            publisher.publish(institution_id=a_id, metric=metric, approved_by="TEST-SYSTEM")
            metric_b = BankMetric(metric.metric_name, metric.period_start,
                                  metric.period_end, 99, 100)
            publisher.publish(institution_id=b_id, metric=metric_b, approved_by="TEST-SYSTEM")
            for bank_login, password, expected_value in (
                (a_login, password_a, 25), (b_login, password_b, 99)
            ):
                bank_dsn = make_conninfo(_DSN, user=bank_login, password=password)
                bank_db = PostgresDatabase(psycopg_connection_factory(bank_dsn))
                metrics = PostgresBankMetricsReader(bank_db).list_metrics()
                self.assertEqual([m.metric_value for m in metrics], [expected_value])
                with self.assertRaises(Exception):
                    with bank_db.transaction() as connection, connection.cursor() as cursor:
                        cursor.execute("SELECT * FROM railone.route_decision_records LIMIT 1")
        finally:
            # Role setup is restricted to a disposable CI database with a
            # privileged migrator; remove test role grants and mappings afterward.
            with database.transaction() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM railone.bank_analytics_principals WHERE login_role IN (%s,%s)",
                    (a_login, b_login),
                )
                for name in (a_login, b_login):
                    cursor.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(name)))
                cursor.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(read_role)))
                cursor.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(read_role)))

    def test_api_security_stores_round_trip(self):
        from railone_api import (
            AccessTokenError,
            AccessTokenService,
            ActorScopes,
            ApiRequest,
            AuthenticatedRequestGuard,
            PrincipalType,
        )

        now = datetime(2026, 7, 14, 19, 30, tzinfo=timezone.utc)
        keys = InMemoryEd25519KeyProvider()
        keys.generate(
            key_id="R1AUTH:live", owner_id="R1AUTH",
            purpose=KeyPurpose.ACCESS_TOKEN_SIGNING,
            not_before=now - timedelta(days=1), not_after=now + timedelta(days=30),
        )
        keys.generate(
            key_id="R1CORE:audit-live", owner_id="R1CORE",
            purpose=KeyPurpose.API_AUDIT_SIGNING,
            not_before=now - timedelta(days=1), not_after=now + timedelta(days=30),
        )
        database = PostgresDatabase(self.factory)
        revocations = PostgresTokenRevocationStore(database)
        tokens = AccessTokenService(
            keys=keys, issuer="railone-live-test", revocations=revocations
        )
        token = tokens.issue(
            principal_id="LIVE-USER-001", principal_type=PrincipalType.HUMAN,
            scopes=ActorScopes(merchant_ids=("MER002",)), key_id="R1AUTH:live",
            token_id="AT-LIVE-001", at=now,
        )
        guard = AuthenticatedRequestGuard(
            tokens=tokens, rate_limits=PostgresRateLimitStore(database),
            audits=PostgresApiAuditStore(database), signatures=SignatureService(keys),
            audit_signing_key_id="R1CORE:audit-live",
        )
        result, decision = guard.execute(
            bearer_token=token,
            request=ApiRequest(
                "REQ-LIVE-AUTH-001", "GET", "/v1/auth/me"
            ),
            operation=lambda principal: principal.principal_id,
            at=now + timedelta(seconds=1),
        )
        self.assertEqual(result, "LIVE-USER-001")
        self.assertTrue(decision.allowed)
        tokens.revoke(
            token=token, reason="LIVE_TEST_COMPLETE", at=now + timedelta(seconds=2)
        )
        with self.assertRaises(AccessTokenError):
            tokens.verify(token, at=now + timedelta(seconds=3))

        with database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) AS count FROM railone.api_request_audit WHERE request_id=%s",
                ("REQ-LIVE-AUTH-001",),
            )
            self.assertEqual(cursor.fetchone()["count"], 1)


if __name__ == "__main__":
    unittest.main()
