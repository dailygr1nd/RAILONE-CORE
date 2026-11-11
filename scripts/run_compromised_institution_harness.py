"""Emit an actionable, redacted JSON-lines institutional compromise report.

Usage: python scripts/run_compromised_institution_harness.py
This is a synthetic sandbox harness. Its events are in-memory audit observations;
use the disposable PostgreSQL integration test to validate durable storage.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.test_compromised_institution_harness import CompromisedInstitutionHarnessTests


CASES = (
    "test_00_strict_idempotency_cannot_return_legacy_p2p_utt",
    "test_01_sender_first_bilateral_to_signed_utt_and_rtt",
    "test_02_missing_receiver_approval_blocks_utt",
    "test_02_missing_receiver_approval_blocks_utt",
    "test_04_receiver_signature_tampering_fails_and_is_audited",
    "test_05_receiver_authority_cannot_be_replayed_on_another_quote",
    "test_07_revoked_receiver_key_blocks_plan",
    "test_08_mutated_persisted_etk_blocks_rtt_after_plan",
    "test_09_route_endpoint_substitution_not_eligible",
    "test_10_bilateral_authority_expiration_blocks_new_rtt",
    "test_12_compromised_adapter_cannot_redirect_resolved_beneficiary",
    "test_13_unknown_provider_outcome_must_keep_economic_hold",
    "test_14_non_idempotent_crash_never_redispatches",
    "test_15_receiver_consent_without_sender_signature_cannot_mint_utt",
    "test_16_rogue_valid_signer_cannot_claim_sender_authority",
    "test_17_receiver_must_bind_exact_existing_sender_etk",
    "test_18_receiver_cannot_precede_sender",
    "test_19_sender_signature_required_before_receiver_acceptance",
    "test_20_receiver_binding_substitution_denied_during_acceptance",
)


def main() -> int:
    failures = 0
    for name in CASES:
        f = CompromisedInstitutionHarnessTests(name)
        try:
            f.setUp()
            getattr(f, name)()
            result = "PASS"
            details = {}
        except Exception as exc:
            failures += 1
            result = "FAIL"
            details = {"exception_type": type(exc).__name__}
        record = {
            "scenario": name.removeprefix("test_"),
            "result": result,
            "created_utts": len(f.contracts._utts),
            "created_rtts": len(f.executions._attempts),
            "redacted_audit_events": f.audit.events,
            **details,
        }
        print(json.dumps(record, sort_keys=True))
    print(json.dumps({"suite": "RAILONE_COMPROMISED_INSTITUTION_V3",
                      "cases": len(CASES), "failed": failures,
                      "outcome": "PASS" if failures == 0 else "FAIL"}))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
