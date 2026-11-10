"""Fail-closed fencing and bank-publication contract tests (no live DB required)."""
from __future__ import annotations

import unittest
from contextlib import contextmanager
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

from railone_crypto import InMemoryEd25519KeyProvider, KeyPurpose, SignatureService
from railone_crypto.signature_service import ArtifactType
from railone_postgres.bank_analytics import (
    BankMetric, PostgresBankMetricsReader, PostgresBankMetricsPublisher,
)
from railone_postgres.fencing import EconomicFenceViolation, PostgresEconomicEffectFence

NOW = datetime(2026, 11, 10, 8, 0, tzinfo=timezone.utc)


class FakeCursor:
    def __init__(self, selected):
        self.selected = list(selected)
        self.executed = []
        self.rowcount = 1

    def execute(self, query, params=()):
        self.executed.append((query, params))
        return self

    def fetchone(self):
        return self.selected.pop(0) if self.selected else None

    def fetchall(self):
        return self.selected.pop(0) if self.selected else []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeDatabase:
    def __init__(self, selected=()):
        self._cursor = FakeCursor(selected)
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return self._cursor

    @contextmanager
    def transaction(self):
        try:
            yield self
            self.commits += 1
        except BaseException:
            self.rollbacks += 1
            raise


def signed_no_effect(signatures, *, key_id="fence-signer", rtt="RTT-TEST", utt="UTT-TEST",
                     provider="PROVIDER-ONE", finding="NO_ECONOMIC_EFFECT"):
    return signatures.sign_artifact(
        artifact_type=ArtifactType.NO_EFFECT_EVIDENCE, key_id=key_id,
        payload={
            "evidence_id": "EVID-TEST", "utt_id": utt, "rtt_id": rtt,
            "provider_id": provider, "finding": finding,
            "source_evidence_digest": hashlib.sha256(b"SYNTHETIC-SIGNED-PROVIDER-EVIDENCE").hexdigest(),
            "observed_at_epoch": int(NOW.timestamp()),
        }, issued_at=NOW,
    )


def signer_fixture():
    keys = InMemoryEd25519KeyProvider()
    for key_id, purpose in (("fence-signer", KeyPurpose.SETTLEMENT_SIGNING),
                            ("other-settlement-key", KeyPurpose.SETTLEMENT_SIGNING)):
        keys.generate(key_id=key_id, owner_id="RAILONE-RECONCILIATION",
                      purpose=purpose,
                      not_before=NOW - timedelta(days=1),
                      not_after=NOW + timedelta(days=1))
    return SignatureService(keys)


class EconomicFenceTests(unittest.TestCase):
    def setUp(self):
        self.signatures = signer_fixture()

    def fence(self, database):
        return PostgresEconomicEffectFence(
            database, signatures=self.signatures,
            trusted_no_effect_signing_keys=frozenset({"fence-signer"}),
        )

    def test_reservation_locks_utt_before_dispatch_and_writes_per_rtt(self):
        db = FakeDatabase(selected=({"utt_id":"UTT-TEST"}, None, {"rtt_id":"RTT-TEST"}, None))
        self.fence(db).reserve_dispatch(
            utt_id="UTT-TEST", rtt_id="RTT-TEST", fence_epoch=1,
            release_evidence_ref=None, request_sha256="a" * 64, at=NOW,
        )
        sql = [query for query, _ in db._cursor.executed]
        self.assertIn("FOR UPDATE", sql[0])
        self.assertIn("accepted_utts", sql[0])
        self.assertIn("INSERT INTO railone.utt_economic_fences", sql[4])
        self.assertIn("INSERT INTO railone.rtt_operational_fences", sql[5])
        self.assertIn("INSERT INTO railone.economic_fence_events", sql[6])
        self.assertEqual(db.commits, 1)

    def test_held_utt_rejects_second_rtt_even_on_new_process(self):
        db = FakeDatabase(selected=({"utt_id":"UTT-TEST"}, None, {"rtt_id":"RTT-OTHER"},
                                    {"state":"HELD","fence_epoch":1,
                                     "last_release_evidence_id":None}))
        with self.assertRaises(EconomicFenceViolation):
            self.fence(db).reserve_dispatch(
                utt_id="UTT-TEST", rtt_id="RTT-OTHER", fence_epoch=1,
                release_evidence_ref=None, request_sha256="a" * 64, at=NOW,
            )
        self.assertEqual(db.commits, 0)
        self.assertEqual(db.rollbacks, 1)
        self.assertEqual(len(db._cursor.executed), 4)

    def test_stale_epoch_and_unproven_release_denied(self):
        for row, epoch, release in (
            (None, 2, None),
            ({"state":"OPEN","fence_epoch":2,"last_release_evidence_id":"EVID-1"}, 1, None),
            ({"state":"OPEN","fence_epoch":2,"last_release_evidence_id":"EVID-1"}, 2, "EVID-WRONG"),
        ):
            with self.subTest(row=row):
                with self.assertRaises(EconomicFenceViolation):
                    PostgresEconomicEffectFence._assert_epoch(
                        row, epoch=epoch, release_ref=release
                    )

    def test_release_requires_verified_purpose_specific_signer(self):
        db = FakeDatabase()
        fence = self.fence(db)
        with self.assertRaises(EconomicFenceViolation):
            fence.release_verified_no_effect(
                evidence=signed_no_effect(self.signatures, key_id="other-settlement-key"),
                at=NOW,
            )
        with self.assertRaises(EconomicFenceViolation):
            fence.release_verified_no_effect(
                evidence=signed_no_effect(self.signatures, finding="SETTLED"),
                at=NOW,
            )
        self.assertFalse(db._cursor.executed)

    def test_verified_no_effect_advances_epoch_and_keeps_signed_proof(self):
        db = FakeDatabase(selected=(
            {"utt_id":"UTT-TEST"},
            {"fence_epoch":1,"current_rtt_id":"RTT-TEST"},
            {"provider_id":"PROVIDER-ONE"}, None,
        ))
        epoch = self.fence(db).release_verified_no_effect(
            evidence=signed_no_effect(self.signatures), at=NOW,
        )
        self.assertEqual(epoch, 2)
        sql = "\n".join(query for query, _ in db._cursor.executed)
        self.assertIn("INSERT INTO railone.economic_fence_no_effect_evidence", sql)
        self.assertIn("state='OPEN'", sql)
        self.assertIn("VERIFIED_NO_EFFECT", str(db._cursor.executed))
        self.assertEqual(db.commits, 1)

    def test_provider_acceptance_is_not_release(self):
        db = FakeDatabase(selected=({"fence_epoch":1},))
        self.fence(db).record_provider_outcome(
            utt_id="UTT-TEST", rtt_id="RTT-TEST", outcome="ACCEPTED", at=NOW
        )
        sql = "\n".join(query for query, _ in db._cursor.executed)
        self.assertIn("ACCEPTED_FOR_PROCESSING", str(db._cursor.executed))
        self.assertNotIn("state='OPEN'", sql)
        self.assertEqual(db.commits, 1)


class BankAnalyticsTests(unittest.TestCase):
    def test_bank_metrics_reject_small_cohort_and_subday_windows(self):
        with self.assertRaises(ValueError):
            BankMetric("OWN_UTT_SETTLED_TOTAL", NOW, NOW + timedelta(days=1), 1, 19)
        with self.assertRaises(ValueError):
            BankMetric("OWN_UTT_SETTLED_TOTAL", NOW, NOW + timedelta(hours=1), 1, 20)
        with self.assertRaises(ValueError):
            BankMetric("RAW_ROUTE_COST", NOW, NOW + timedelta(days=1), 1, 20)
        with self.assertRaises(ValueError):
            BankMetric("OWN_PROVIDER_ACCEPTANCE_RATE_BPS", NOW, NOW + timedelta(days=1), 10001, 20)

    def test_bank_reader_never_requests_institution_or_raw_route_table(self):
        metric = BankMetric("OWN_UTT_SETTLED_TOTAL", NOW, NOW + timedelta(days=1), 40, 100)
        db = FakeDatabase(selected=([dict(metric_name=metric.metric_name,
                                         period_start=metric.period_start,
                                         period_end=metric.period_end,
                                         metric_value=metric.metric_value,
                                         sample_count=metric.sample_count)],))
        self.assertEqual(PostgresBankMetricsReader(db).list_metrics(), (metric,))
        query, params = db._cursor.executed[0]
        self.assertIn("railone_bank.metrics", query)
        self.assertNotIn("route_decision_records", query)
        self.assertNotIn("institution_id", query)
        self.assertEqual(params, (100,))

    def test_publisher_accepts_only_structured_approved_metrics(self):
        metric = BankMetric("OWN_UTT_SETTLED_TOTAL", NOW, NOW + timedelta(days=1), 20, 20)
        db = FakeDatabase()
        pub = PostgresBankMetricsPublisher(db)
        self.assertTrue(pub.publish(institution_id="BANK-001",metric=metric,
                                    approved_by="SECURITY-REVIEWER").startswith("PUB-"))
        sql = db._cursor.executed[0][0]
        self.assertIn("railone.bank_analytics_publications", sql)
        self.assertNotIn("route_decision_records", sql)

    def test_migration_declares_rls_and_no_shared_bank_role_read_access(self):
        root = Path(__file__).resolve().parents[1]
        sql = (root / "migrations/0015_durable_effect_fences_and_bank_analytics.sql").read_text()
        for marker in (
            "FORCE ROW LEVEL SECURITY", "security_barrier=true", "session_user",
            "REVOKE ALL ON SCHEMA railone FROM PUBLIC",
            "CREATE TABLE railone.utt_economic_fences",
            "CREATE TABLE railone.rtt_operational_fences",
        ):
            self.assertIn(marker, sql)
        self.assertNotIn("GRANT SELECT ON railone.route_decision_records", sql)


if __name__ == "__main__":
    unittest.main()
