from __future__ import annotations

import json
import unittest
from dataclasses import replace

from railone_operations import ProviderExecutionRequest, ProviderOutcome
from railone_sandbox import (
    EffectScenario, SandboxEffectWorker, build_local_simulated_runtime,
)


def request(*, provider="BANK-KE", rail="DOMESTIC_BANK", rtt="RTT-001"):
    return ProviderExecutionRequest(
        idempotency_key=f"IDEM-{rtt}", request_sha256=f"hash-{rtt}",
        utt_id="UTT-001", rtt_id=rtt, attempt_number=1,
        provider_id=provider, rail=rail, amount_minor=10_000,
        currency_from="KES", receive_amount_minor=10_000, currency_to="KES",
        payer_account_reference="SIM-PAYER-001",
        beneficiary_account_reference="SIM-BENEFICIARY-001",
    )


class SandboxRuntimeTests(unittest.TestCase):
    def test_local_runtime_is_explicitly_degraded_but_usable_for_tests(self):
        runtime = build_local_simulated_runtime()
        self.assertEqual(runtime.readiness()["status"], "READY")
        self.assertEqual(runtime.readiness()["key_boundary"], "SIMULATION_MEMORY")
        self.assertTrue(runtime.readiness()["synthetic_effects_only"])

    def test_bank_success_is_acceptance_then_separate_settlement_effect(self):
        runtime = build_local_simulated_runtime()
        result = runtime.bank_adapter.submit(request())
        self.assertEqual(result.outcome, ProviderOutcome.ACCEPTED)
        self.assertEqual(runtime.effects.current_tick, 0)
        effects = runtime.effects.advance()
        self.assertEqual(len(effects), 1)
        self.assertEqual(effects[0].effect_type, "SETTLED")
        self.assertEqual(json.loads(effects[0].payload)["rtt_id"], "RTT-001")

    def test_mpesa_timeout_then_success_is_deterministic_and_daraja_shaped(self):
        runtime = build_local_simulated_runtime()
        runtime.effects.set_scenario(
            rtt_id="RTT-MPESA", scenario=EffectScenario.TIMEOUT_THEN_SUCCESS
        )
        item = request(provider="MPESA-KE", rail="MOBILE_MONEY", rtt="RTT-MPESA")
        result = runtime.mpesa_adapter.submit(item)
        self.assertEqual(result.outcome, ProviderOutcome.ACCEPTED)
        first = runtime.effects.advance()
        second = runtime.effects.advance()
        self.assertEqual(first[0].effect_type, "TIMEOUT")
        self.assertEqual(second[0].effect_type, "SETTLED")
        body = json.loads(second[0].payload)
        self.assertEqual(body["Result"]["ConversationID"], result.external_reference)
        self.assertEqual(body["Result"]["ResultCode"], 0)

    def test_unknown_and_rejections_do_not_schedule_settlement(self):
        for index, scenario in enumerate((
            EffectScenario.UNKNOWN_AFTER_SEND,
            EffectScenario.REJECTED_RETRYABLE,
            EffectScenario.REJECTED_TERMINAL,
        )):
            runtime = build_local_simulated_runtime()
            rtt = f"RTT-{index}"
            runtime.effects.set_scenario(rtt_id=rtt, scenario=scenario)
            result = runtime.bank_adapter.submit(request(rtt=rtt))
            self.assertNotEqual(result.outcome, ProviderOutcome.ACCEPTED)
            self.assertEqual(runtime.effects.advance(), ())

    def test_idempotency_replay_is_stable_and_changed_material_fails(self):
        runtime = build_local_simulated_runtime()
        item = request()
        first = runtime.bank_adapter.submit(item)
        self.assertEqual(runtime.bank_adapter.submit(item), first)
        with self.assertRaisesRegex(RuntimeError, "idempotency"):
            runtime.bank_adapter.submit(replace(item, request_sha256="changed"))

    def test_non_synthetic_endpoints_are_refused(self):
        runtime = build_local_simulated_runtime()
        with self.assertRaises(PermissionError):
            runtime.bank_adapter.submit(replace(
                request(), beneficiary_account_reference="254700000001"
            ))

    def test_effect_worker_requeues_failure_and_applies_on_next_tick(self):
        runtime = build_local_simulated_runtime()
        runtime.bank_adapter.submit(request())

        class Consumer:
            calls = 0

            def apply(self, effect):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("simulated worker crash")

        consumer = Consumer()
        worker = SandboxEffectWorker(
            broker=runtime.effects, consumer=consumer, metrics=runtime.metrics
        )
        self.assertEqual(worker.run_once(), ())
        applied = worker.run_once()
        self.assertEqual(len(applied), 1)
        self.assertEqual(consumer.calls, 2)
        metrics = runtime.metrics.snapshot()
        self.assertEqual(metrics[
            'railone_sandbox_worker_failures_total{effect_type="SETTLED",provider="BANK-KE"}'
        ], 1)


if __name__ == "__main__":
    unittest.main()
