from __future__ import annotations

import unittest

from railone_sandbox import (
    EffectDeliveryState, InMemorySandboxEffectStore, ProviderEffectRecord,
    ScheduledProviderEffect, SupervisorState, WorkerSupervisor,
)


def effect_record() -> ProviderEffectRecord:
    effect = ScheduledProviderEffect(
        effect_id="SIMEFF-001", provider_id="BANK-KE", rtt_id="RTT-001",
        external_reference="SIMREF-001", effect_type="SETTLED",
        provider_code="0", due_tick=1, payload=b'{"event":"SETTLED"}',
    )
    return ProviderEffectRecord(effect=effect, available_tick=1)


class DurableSandboxEffectTests(unittest.TestCase):
    def test_expired_lease_is_reclaimed_and_old_worker_loses_authority(self):
        store = InMemorySandboxEffectStore()
        store.schedule(effect_record())
        first = store.advance_and_claim(
            worker_id="worker-a", ticks=1, lease_ticks=2, limit=10
        )
        self.assertEqual(first[0].state, EffectDeliveryState.IN_FLIGHT)
        self.assertEqual(store.advance_and_claim(
            worker_id="worker-b", ticks=1, lease_ticks=2, limit=10
        ), ())
        reclaimed = store.advance_and_claim(
            worker_id="worker-b", ticks=1, lease_ticks=2, limit=10
        )
        self.assertEqual(reclaimed[0].delivery_attempts, 2)
        with self.assertRaises(PermissionError):
            store.mark_delivered(effect_id="SIMEFF-001", worker_id="worker-a")
        delivered = store.mark_delivered(
            effect_id="SIMEFF-001", worker_id="worker-b"
        )
        self.assertEqual(delivered.state, EffectDeliveryState.DELIVERED)

    def test_effect_moves_to_dead_letter_after_attempt_cap(self):
        store = InMemorySandboxEffectStore()
        store.schedule(effect_record())
        store.advance_and_claim(
            worker_id="worker", ticks=1, lease_ticks=1, limit=10
        )
        pending = store.reschedule(
            effect_id="SIMEFF-001", worker_id="worker", delay_ticks=1,
            error="first failure", max_attempts=2,
        )
        self.assertEqual(pending.state, EffectDeliveryState.PENDING)
        store.advance_and_claim(
            worker_id="worker", ticks=1, lease_ticks=1, limit=10
        )
        terminal = store.reschedule(
            effect_id="SIMEFF-001", worker_id="worker", delay_ticks=1,
            error="second failure", max_attempts=2,
        )
        self.assertEqual(terminal.state, EffectDeliveryState.DEAD_LETTER)

    def test_supervisor_reports_repeated_top_level_failures(self):
        class BrokenWorker:
            def run_once(self):
                raise RuntimeError("database unavailable")

        supervisor = WorkerSupervisor(BrokenWorker(), failure_threshold=2)
        supervisor.tick()
        self.assertEqual(supervisor.status().state, SupervisorState.RUNNING)
        supervisor.tick()
        self.assertEqual(supervisor.status().state, SupervisorState.DEGRADED)
        supervisor.stop()
        self.assertEqual(supervisor.status().state, SupervisorState.STOPPED)


if __name__ == "__main__":
    unittest.main()
