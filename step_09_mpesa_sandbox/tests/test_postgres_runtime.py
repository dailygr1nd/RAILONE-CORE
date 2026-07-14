from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path

from railone_execution.models import (
    ExecutionPlan,
    LinkStatus,
    PlanStatus,
    RankedRoute,
    RouteCandidate,
)
from railone_postgres.codec import plan_from_row, plan_snapshot, plan_state
from railone_postgres.migrations import _transaction_body
from railone_postgres.runtime import PostgresDatabase


class FakeConnection:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


class PostgresRuntimeTests(unittest.TestCase):
    def test_transaction_commits_and_closes(self):
        connection = FakeConnection()
        with PostgresDatabase(lambda: connection).transaction() as opened:
            self.assertIs(opened, connection)
        self.assertEqual(connection.commits, 1)
        self.assertEqual(connection.rollbacks, 0)
        self.assertTrue(connection.closed)

    def test_transaction_rolls_back_and_closes(self):
        connection = FakeConnection()
        with self.assertRaisesRegex(RuntimeError, "boom"):
            with PostgresDatabase(lambda: connection).transaction():
                raise RuntimeError("boom")
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(connection.closed)

    def test_plan_codec_separates_immutable_snapshot_from_mutable_state(self):
        now = datetime(2026, 7, 14, 18, 0, tzinfo=timezone.utc)
        candidate = RouteCandidate(
            route_id="MPESA", source_institution_id="BANK-001",
            destination_institution_id="MNO-001", rail="MOBILE_MONEY",
            provider="MPESA-KE", adapter="mpesa-sandbox-v1",
            currency_from="KES", currency_to="KES", min_amount_minor=100,
            max_amount_minor=1_000_000, latency_ms=500, congestion_bps=100,
            liquidity_capacity_minor=5_000_000, throughput_headroom_bps=9000,
            speed_bps=8500, estimated_cost_minor=30, link_status=LinkStatus.UP,
            telemetry_observed_at=now, telemetry_expires_at=now.replace(minute=5),
        )
        ranked = RankedRoute(candidate, 9000, (("cost", 9000),), 1)
        plan = ExecutionPlan(
            plan_id="PLAN-001", utt_id="UTT-001", ranked_routes=(ranked,),
            remaining_route_ids=("MPESA",), failures=(), attempts_used=0,
            max_attempts=3, routing_budget_minor=100,
            routing_cost_spent_minor=0, current_rtt_id=None,
            previous_rtt_id=None, previous_route_id=None,
            status=PlanStatus.ACTIVE, successful_route_id=None, version=1,
            created_at=now, updated_at=now,
        )
        row = {
            "plan_id": plan.plan_id, "utt_id": plan.utt_id,
            "plan_snapshot": plan_snapshot(plan), "plan_state": plan_state(plan),
            "status": plan.status.value, "attempts_used": plan.attempts_used,
            "max_attempts": plan.max_attempts,
            "routing_budget_minor": plan.routing_budget_minor,
            "routing_cost_spent_minor": plan.routing_cost_spent_minor,
            "current_rtt_id": None, "previous_rtt_id": None,
            "successful_route_id": None, "version": 1,
            "created_at": now, "updated_at": now,
        }
        restored = plan_from_row(row)
        self.assertEqual(restored, plan)
        self.assertNotIn("remaining_route_ids", plan_snapshot(plan))
        self.assertIn("remaining_route_ids", plan_state(plan))

    def test_migration_runner_removes_embedded_transaction_wrapper(self):
        self.assertEqual(_transaction_body("\nBEGIN;\nSELECT 1;\nCOMMIT;\n"), "SELECT 1;")

    def test_step_07_migration_contains_cas_projection_and_plan_state(self):
        root = Path(__file__).resolve().parents[1]
        sql = (root / "migrations" / "0003_postgres_runtime_projection.sql").read_text()
        self.assertIn("plan_state jsonb", sql)
        self.assertIn("projection_inbox", sql)
        self.assertIn("submission_version <= OLD.submission_version", sql)
        operations = (root / "railone_postgres" / "operations.py").read_text()
        self.assertIn("FOR UPDATE SKIP LOCKED", operations)

    def test_step_08_migration_contains_revocation_rate_limit_and_signed_audit(self):
        root = Path(__file__).resolve().parents[1]
        sql = (root / "migrations" / "0004_authenticated_api_security.sql").read_text()
        self.assertIn("api_token_revocations", sql)
        self.assertIn("api_rate_limit_windows", sql)
        self.assertIn("api_request_audit", sql)
        self.assertIn("api_request_audit_append_only", sql)

    def test_step_09_migration_persists_provider_context_and_reconciliation(self):
        root = Path(__file__).resolve().parents[1]
        sql = (root / "migrations" / "0005_mpesa_callback_reconciliation.sql").read_text()
        self.assertIn("provider_context jsonb", sql)
        self.assertIn("RECONCILIATION_REQUIRED", sql)
        self.assertIn("reconciled RTT must become failed or succeeded", sql)
        callbacks = (root / "railone_postgres" / "callbacks.py").read_text()
        self.assertIn("ON CONFLICT (provider_id, provider_event_id) DO NOTHING", callbacks)


if __name__ == "__main__":
    unittest.main()
