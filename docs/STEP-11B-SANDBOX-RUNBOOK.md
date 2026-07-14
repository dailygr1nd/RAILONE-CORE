# Step 11B encrypted sandbox runbook

## Purpose

Run production-shaped execution semantics against deterministic synthetic bank
and M-PESA effects. No live funds, customer data, partner credentials, or
production endpoints are permitted.

## Local verification

```powershell
python -m pip install -e ".[pilot]"
python .\scripts\check_repository_convergence.py
python .\scripts\check_no_secrets.py
python .\run_tests.py
```

## Runtime composition

`build_local_simulated_runtime()` generates volatile in-process KEKs. It is for
developer tests only and reports `SIMULATION_MEMORY` readiness.

A deployed sandbox uses `compose_pilot_runtime()` with:

- a `RemoteKeyEncryptionProvider` backed by an isolated KMS/HSM service;
- `PostgresEncryptedSecretStore` after migration `0007`;
- separate active KEK ids for account endpoints, contacts, credentials, and
  notification bodies; and
- `PilotRuntimeConfig(require_isolated_keys=True)`.

The readiness result must be `READY`, `synthetic_effects_only` must be `true`,
and `key_boundary` must be `ISOLATED` before shared sandbox traffic.

## Synthetic endpoint policy

Both payer and beneficiary provider references must start with `SIM-`. The
effect broker refuses any other value. Use opaque account-binding identifiers
in quotes and UTTs; register the `SIM-` endpoint only in the encrypted endpoint
vault.

## Mandatory scenarios

Run each provider through:

1. `SUCCESS`;
2. `REJECTED_RETRYABLE`;
3. `REJECTED_TERMINAL`;
4. `UNKNOWN_AFTER_SEND`; and
5. `TIMEOUT_THEN_SUCCESS`.

For `UNKNOWN_AFTER_SEND`, verify that RailOne does not create a blind retry.
For `TIMEOUT_THEN_SUCCESS`, verify reconciliation is entered before the late
success is applied. Provider acceptance alone must never create settlement SMS.

## Promotion blockers

- any real endpoint or personal data in the sandbox;
- an in-memory key boundary in a shared environment;
- skipped PostgreSQL, HTTP, or callback tests in CI;
- plaintext sensitive-value persistence;
- unknown outcomes that automatically resubmit; or
- settlement notifications created without signed provider evidence.
