"""Disposable database proof that P2P v2 persists both ETKs before execution.

Never run against production. Requires RAILONE_TEST_DATABASE_URL and
RAILONE_ALLOW_TEST_SCHEMA_RESET=1; integration resets the railone schemas.
"""

from __future__ import annotations

import os
import unittest
from datetime import timedelta
from dataclasses import replace
from pathlib import Path

from railone_authority import ExecutionAuthorityService
from railone_contracts import QuoteAcceptanceService
from railone_contracts.store import IdempotencyConflictError
from railone_execution import ExecutionPlanningService, RttAttemptService
from railone_postgres import (
    PostgresContractStore, PostgresDatabase, PostgresExecutionStore,
    MigrationRunner, psycopg_connection_factory,
)
from railone_postgres.security_incidents import PostgresSecurityAuditStore
import tests.test_compromised_institution_harness as synthetic


_DSN = os.environ.get("RAILONE_TEST_DATABASE_URL", "")
_RESET = os.environ.get("RAILONE_ALLOW_TEST_SCHEMA_RESET") == "1"


@unittest.skipUnless(_DSN and _RESET, "disposable PostgreSQL required")
class BilateralPostgresLiveTests(unittest.TestCase):
    def test_sender_first_persists_etk_s_and_etk_r_and_blocks_compromise(self):
        # Fixtures are shared only for cryptographic inputs. No in-memory
        # execution store is used for the actual database operations.
        fixture = synthetic.CompromisedInstitutionHarnessTests("test_01_sender_first_bilateral_to_signed_utt_and_rtt")
        fixture.setUp()
        connect = psycopg_connection_factory(_DSN)
        connection = connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute("DROP SCHEMA IF EXISTS railone_bank CASCADE")
                cursor.execute("DROP SCHEMA IF EXISTS railone CASCADE")
            connection.commit()
        finally:
            connection.close()
        MigrationRunner(connection_factory=connect, migrations_directory=Path(__file__).resolve().parents[1]/"migrations").apply_all()
        database = PostgresDatabase(connect)
        contracts = PostgresContractStore(database)
        executions = PostgresExecutionStore(database)
        audit = PostgresSecurityAuditStore(database)
        acceptance = QuoteAcceptanceService(
            signatures=fixture.signatures, authority=ExecutionAuthorityService(fixture.signatures),
            store=contracts, utt_signing_key_id="core", authority_signing_key_id="core",
            require_bilateral_p2p=True, security_audit=audit,
        )
        sender = fixture.sender()
        receiver = fixture.receiver(sender)
        contract = acceptance.accept(fixture.command(receiver, sender=sender), at=fixture.now+timedelta(seconds=10)).contract
        stored_sender, stored_receiver = contracts.require_bilateral_authorities(contract.utt_id)
        self.assertEqual(stored_receiver.payload["etk_r_id"], receiver.payload["etk_r_id"])
        self.assertEqual(stored_receiver.payload["etk_s_digest"], sender.protected["payload_sha256"])
        self.assertEqual(contracts.require_utt(contract.utt_id).payload["authority_version"], 4)
        plan = ExecutionPlanningService(
            signatures=fixture.signatures, contracts=contracts, executions=executions,
        ).build_plan(utt_id=contract.utt_id, candidates=(fixture.route(),),
                     at=fixture.now+timedelta(seconds=11))
        attempt = RttAttemptService(
            signatures=fixture.signatures, contracts=contracts,
            executions=executions, rtt_signing_key_id="core",
            endpoints=fixture.directory,
        ).start_next(utt_id=contract.utt_id, at=fixture.now+timedelta(seconds=12))
        self.assertEqual(attempt.plan_id, plan.plan_id)
        with database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT authority_type FROM railone.execution_authorities WHERE utt_id=%s ORDER BY authority_type", (contract.utt_id,))
            self.assertEqual([row["authority_type"] for row in cursor.fetchall()], ["ETK_R", "ETK_S"])
        # A distinct, tampered acceptance must be rejected and journaled; it
        # cannot create a second UTT or enter institutional dispatch.
        new_quote = fixture.make_quote(replace(fixture.terms, request_id="REQ-ATTACKED", amount_minor=200000))
        # Reusing the original idempotency key must fail before verification.
        with self.assertRaises(IdempotencyConflictError):
            acceptance.accept(
                fixture.command(receiver, quote=new_quote, sender=sender),
                at=fixture.now+timedelta(seconds=10),
            )
        # A *fresh* request key reaches bilateral verification, which must
        # reject a changed quote paired with the old sender's signature.
        malicious = replace(
            fixture.command(receiver, quote=new_quote, sender=sender),
            idempotency_key="IDEM-P2P-ATTACK-FRESH",
        )
        with self.assertRaisesRegex(PermissionError, "SENDER_QUOTE_BINDING_MISMATCH"):
            acceptance.accept(malicious, at=fixture.now+timedelta(seconds=10))
        with database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT reason_code FROM railone.institution_security_audit ORDER BY occurred_at DESC LIMIT 1")
            self.assertEqual(cursor.fetchone()["reason_code"], "SENDER_QUOTE_BINDING_MISMATCH")
            cursor.execute("SELECT COUNT(*) AS n FROM railone.accepted_utts")
            self.assertEqual(cursor.fetchone()["n"], 1)


if __name__ == "__main__":
    unittest.main()
