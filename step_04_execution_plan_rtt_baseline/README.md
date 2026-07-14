# RailOne Pilot Convergence - Step 04

This cumulative batch contains the cryptographic, identity, and execution-
authority and commercial-contract baselines. It adds deterministic execution
planning, signed RTT birth artifacts, retry lineage, and explicit failure
dispositions.

## What this step locks

- Ed25519 is the canonical signature algorithm for RailOne-owned artifacts.
- Ed25519 signs data; it does not encrypt data.
- Private keys are never stored in the repository or returned by the key
  registry.
- Every signature carries an algorithm, curve, key identifier, artifact type,
  version, issuer, issue time, and payload hash.
- Quote, execution, identity, settlement, and replay signing are separate key
  purposes.
- JSON payloads are serialized deterministically and floating-point numbers are
  rejected from signed financial artifacts.
- Key rotation and revocation are part of verification semantics.
- A RailOne continuity identifier is derived from a versioned keyed digest and
  contains 160 bits of collision-resistant output.
- Raw national identifiers and raw provider subject identifiers are not stored
  in identity continuity objects.
- RIG is immutable genesis evidence, RIO is the stable public continuity object,
  and RIV contains mutable trust evolution.
- Institutional identity claims require a valid Ed25519 attestation.
- ETK-S is a signed sender execution-authority attestation bound to a UTT and
  accepted quote.
- ETK-R is signed receiver participation or eligibility evidence and cannot be
  fabricated merely by hashing ETK-S.
- Passive-credit and pre-authorized beneficiary flows do not falsely claim that
  a receiver actively confirmed.
- A quote is a signed, expiring commercial offer and does not bind execution to
  a specific rail.
- A UTT can only be created after explicit acceptance of a valid quote.
- Quote acceptance creates the UTT and ETK-S as one atomic contract record.
- One accepted quote cannot produce multiple UTTs.
- Idempotency-key reuse with different request material is rejected.
- UTT commercial payloads and signed envelopes are deeply immutable in memory.
- Customer pricing is `PER_INTENT`, preserving one charge across all future RTT
  attempts.
- An ExecutionPlan can only be created for a persisted, valid signed UTT.
- Route eligibility rejects down links, stale or future telemetry, currency and
  amount mismatches, insufficient liquidity, and routes outside the budget.
- Route ranking is deterministic, integer-only, and uses a stable route-ID tie
  break.
- Every RTT is Ed25519-signed and preserves its UTT, plan, attempt, prior RTT,
  and prior route lineage.
- An RTT is an immutable birth artifact; outcome state evolves in a separate
  attempt record.
- Retryable, terminal, and reconciliation-required failures are distinct.
- Unknown provider outcomes block retry to prevent duplicate payments.
- The UTT holds the one customer charge; RTTs contain no customer-fee fields.

## Files

- `docs/ADR-001-railone-pilot-baseline.md` - authoritative architecture decision.
- `railone_crypto/canonical_json.py` - strict deterministic JSON encoding.
- `railone_crypto/key_provider.py` - key metadata and signer/registry contracts.
- `railone_crypto/signature_service.py` - signed artifact envelopes and verification.
- `tests/test_signature_service.py` - deterministic, tamper, purpose, lifecycle,
  and serialization tests.
- `railone_identity/` - deterministic continuity and attestation validation.
- `railone_authority/` - signed ETK-S and ETK-R issuance.
- `tests/test_identity_continuity.py` - identity and attestation tests.
- `tests/test_execution_authority.py` - ETK binding and participation tests.
- `railone_contracts/` - quote, origin-context, acceptance, UTT, and store contracts.
- `tests/test_quote_acceptance.py` - quote and UTT invariant tests.
- `docs/ADR-004-execution-plan-and-rtt.md` - authoritative Step 04 decision.
- `railone_execution/models.py` - immutable route, plan, failure, and RTT records.
- `railone_execution/scoring.py` - deterministic eligibility and route scoring.
- `railone_execution/store.py` - transactional persistence boundary and test adapter.
- `railone_execution/service.py` - plan construction and RTT lifecycle services.
- `tests/test_execution_plan_rtt.py` - routing, retry, lineage, and safety tests.
- `pyproject.toml` - editable-install metadata and runtime dependency declaration.

## Run the tests

From this directory:

```bash
python run_tests.py
```

From the parent `RAILONE PROTOTYPE` directory in PowerShell:

```powershell
python .\step_04_execution_plan_rtt_baseline\run_tests.py
```

For an editable local installation, run this once inside the Step 04 directory:

```powershell
python -m pip install -e .
```

That makes the `railone_*` packages importable for direct scripts as well as
through the bundled runner.

Do not use `python -m unittest discover -s tests` from the parent directory;
there is no parent-level `tests` package. The runner resolves the Step 04 project
root automatically and avoids the `ModuleNotFoundError` seen when a nested test
file is invoked directly without installing the package.

The implementation uses the already-pinned `cryptography` package.

## Integration rule

Do not connect this batch to the legacy `crypto/keys/*.json` files. Those keys
were present in the uploaded repository snapshot and must be treated as
compromised. Production integration must supply a `SigningKeyProvider` backed
by an isolated signer, HSM, KMS-compatible service, or Vault-like service.

The in-memory signing and continuity-secret providers are explicitly test-only.
Production adapters must use isolated key services and a durable repository with
a unique constraint on the keyed identity fingerprint.

Step 05 should add durable SQL repository contracts, append-only signed
execution events, normalized provider adapter outcomes, and reconciliation
release controls before any live-value pilot.
