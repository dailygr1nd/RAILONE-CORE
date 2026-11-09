# RailOne v0.15.1 — Pilot baseline reproducibility patch

**Source**: user-provided RailOne Core v0.15.0 Repomix snapshot, July 14, 2026; the three source files are from the *top-level current tree*, not historical step folders.

## Changes

1. `railone_certification/runner.py` — add dependency-injected timezone-aware completion clock; runtime defaults to real UTC. This preserves the distinction between event start and actual finish and rejects naive timestamps.
2. `tests/test_partner_certification_harness.py` — inject a controlled completion clock in the fixed-2026 signing-key test. No signing-window checks are removed or relaxed.
3. `tests/test_institution_adapter_spi.py` — explicitly configure test TLS minimum version 1.2. Production transport continues to fail closed when minimum version is not explicitly configured.

## Apply

From a clean checkout matching the top-level v0.15.0 snapshot:

```bash
git apply --check RailOne_v0.15.1_pilot_baseline_fix.patch
git apply RailOne_v0.15.1_pilot_baseline_fix.patch
python run_tests.py
python scripts/check_no_secrets.py
# Remove generated __pycache__ trees before the strict repository-convergence check.
python scripts/check_repository_convergence.py
```

## Observed checks in the provided workspace

- Unit suite: **159 discovered; 156 passed; 3 skipped; 0 errors**.
- Secret check: passed.
- Repository convergence: passed after removing generated `__pycache__` files.
- Disposable PostgreSQL validation: **NOT RUN**, needs `RAILONE_TEST_DATABASE_URL` and explicit reset approval against an isolated database.
- No partner sandbox, HSM/KMS, bank connectivity, load or real-money validation was performed.

## Non-goals

No changes to UTT, RTT, settlement finality, signature verification, live provider behavior, economic-fence rules, or partner licensing. This patch establishes only test reproducibility and does not certify readiness for production funds.
