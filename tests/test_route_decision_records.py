"""ADR-017 deterministic route-decision evidence and storage semantics."""

from __future__ import annotations

import json
import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta

from railone_execution import LinkStatus, RouteDecisionRecord
from railone_execution.store import ExecutionPlanConflictError
from tests import test_execution_plan_rtt as fixture_module


class RouteDecisionRecordTests(unittest.TestCase):
    def setUp(self):
        # Reuse the repository's real accepted-UTT/quote/signature test fixture.
        self.fixture = fixture_module.ExecutionPlanAndRttTests(methodName="test_unknown_utt_cannot_create_a_plan")
        self.fixture.setUp()
        self.utt_id = self.fixture._accepted_utt()
        self.instant = self.fixture.now + timedelta(seconds=20)
        self.fast = self.fixture._route("FAST", latency_ms=100, cost_minor=100)
        self.slow = self.fixture._route("SLOW", latency_ms=2000, cost_minor=400)
        self.down = self.fixture._route("DOWN", latency_ms=1, cost_minor=1, status=LinkStatus.DOWN)
        self.low = self.fixture._route("NO-LIQUIDITY", latency_ms=1, cost_minor=1, capacity_minor=100)

    def _make(self, candidates=None):
        plan = self.fixture.planning.build_plan(
            utt_id=self.utt_id,
            candidates=candidates if candidates is not None else (self.slow, self.down, self.low, self.fast),
            at=self.instant,
        )
        record = self.fixture.executions.require_decision_for_plan(plan.plan_id)
        return plan, record

    def test_build_plan_persists_one_verifiable_original_decision(self):
        plan, decision = self._make()
        self.assertTrue(decision.decision_id.startswith("RDEC-"))
        self.assertEqual(decision.plan_id, plan.plan_id)
        self.assertEqual(decision.utt_id, self.utt_id)
        self.assertEqual(decision.payload["selected_route_id"], "FAST")
        decision.verify(plan=plan)
        self.assertEqual([row["route_id"] for row in decision.payload["excluded_routes"]],
                         ["DOWN", "NO-LIQUIDITY"])

    def test_no_side_effect_on_rtt_start(self):
        plan, decision = self._make()
        attempt = self.fixture.attempts.start_next(utt_id=self.utt_id, at=self.instant + timedelta(seconds=1))
        self.assertEqual(attempt.route_id, "FAST")
        decision.verify(plan=self.fixture.executions.require_plan(plan.plan_id))

    def test_candidate_input_order_does_not_change_decision(self):
        plan, original = self._make()
        reordered = (self.fast, self.low, self.down, self.slow)
        identical = self.fixture.planning.build_plan(utt_id=self.utt_id, candidates=reordered, at=self.instant)
        self.assertEqual(plan, identical)
        self.assertEqual(self.fixture.executions.require_decision_for_plan(plan.plan_id), original)

    def test_different_input_timestamp_does_not_rewrite_decision(self):
        self._make()
        with self.assertRaises(ExecutionPlanConflictError):
            self.fixture.planning.build_plan(
                utt_id=self.utt_id, candidates=(self.fast, self.slow),
                at=self.instant + timedelta(microseconds=1),
            )

    def test_decision_body_is_immutable_from_caller(self):
        plan, original = self._make()
        material = original.payload
        material["selected_route_id"] = "SLOW"
        self.assertEqual(original.payload["selected_route_id"], "FAST")
        with self.assertRaises(FrozenInstanceError):
            original.decision_sha256 = "0" * 64
        original.verify(plan=plan)

    def test_altered_json_without_hash_fails(self):
        _, original = self._make()
        material = original.payload
        material["selected_route_id"] = "SLOW"
        tampered = replace(original, canonical_body=json.dumps(material, sort_keys=True, separators=(",", ":")))
        with self.assertRaises(ValueError):
            tampered.verify()

    def test_self_consistent_digest_cannot_hide_scoring_tamper(self):
        from railone_execution.decisions import _digest
        from railone_crypto.canonical_json import canonical_json_bytes
        _, original = self._make()
        material = original.payload
        material["ranked_routes"][0]["score_bps"] -= 1
        body = canonical_json_bytes(material)
        digest = _digest(body)
        forged = replace(original, canonical_body=body.decode(),
                         decision_sha256=digest, decision_id="RDEC-" + digest[:32].upper())
        with self.assertRaisesRegex(ValueError, "ranking"):
            forged.verify()

    def test_microsecond_precise_telemetry_roundtrip(self):
        # Rounded second timestamps could otherwise change eligibility at the boundary.
        adjusted = replace(self.fast,
                           telemetry_observed_at=self.instant - timedelta(microseconds=1),
                           telemetry_expires_at=self.instant + timedelta(microseconds=1))
        plan, record = self._make(candidates=(adjusted,))
        record.verify(plan=plan)

    def test_route_exclusion_reasons_use_scorer_predicates(self):
        _, decision = self._make()
        exclusions = {v["route_id"]: v["reasons"] for v in decision.payload["excluded_routes"]}
        self.assertEqual(exclusions["DOWN"], ["LINK_DOWN"])
        self.assertEqual(exclusions["NO-LIQUIDITY"], ["INSUFFICIENT_ROUTE_LIQUIDITY"])

    def test_recomputed_digest_cannot_hide_exclusion_tamper(self):
        from railone_execution.decisions import _digest
        from railone_crypto.canonical_json import canonical_json_bytes
        _, original = self._make()
        material = original.payload
        material["excluded_routes"] = []
        body = canonical_json_bytes(material)
        digest = _digest(body)
        forged = replace(original, canonical_body=body.decode(),
                         decision_sha256=digest, decision_id="RDEC-" + digest[:32].upper())
        with self.assertRaisesRegex(ValueError, "exclusion"):
            forged.verify()

    def test_external_utt_digest_binding_is_enforced(self):
        _, decision = self._make()
        with self.assertRaisesRegex(ValueError, "verified UTT digest"):
            decision.verify(expected_utt_payload_sha256="0" * 64)

    def test_policy_weight_values_are_reproducible(self):
        _, decision = self._make()
        weights = decision.payload["weights_bps"]
        self.assertEqual(sum(weights.values()), 10_000)
        self.assertEqual(decision.payload["scoring_algorithm"], "R1-INTEGER-WEIGHTED-BPS-V1")
        decision.verify()

    def test_migration_is_append_only_and_fk_bound(self):
        from pathlib import Path
        src = (Path(__file__).resolve().parents[1] / "migrations" /
               "0012_immutable_route_decision_records.sql").read_text()
        self.assertIn("CREATE TABLE railone.route_decision_records", src)
        self.assertIn("REFERENCES railone.execution_plans(plan_id)", src)
        self.assertIn("route_decision_records_append_only", src)


if __name__ == "__main__":
    unittest.main()
