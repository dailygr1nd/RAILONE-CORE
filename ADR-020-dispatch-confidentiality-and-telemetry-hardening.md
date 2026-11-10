# ADR-020: Dispatch confidentiality and bounded sandbox telemetry

**Status:** Alpha implementation candidate — not live-money authorized
**Scope:** v0.16 security hardening on top of ADR-019; non-custodial operation unchanged

## Threat model

An attacker who reads PostgreSQL metadata, worker errors or operational metrics
may recover customer contacts, infer routing behavior or learn institution secrets.
A separate attacker may invoke institutional dispatch with an expired or
unverified wrapper in an attempt to make RailOne resolve account endpoints
before the trusted gateway rejects a transaction.

## Decisions

1. **Preflight precedes sensitive resolution.** In `INSTITUTIONAL_SANDBOX`,
   `ProviderSubmissionCoordinator.dispatch()` calls the trusted admission
   gateway's `preflight(rtt_id, at)` before `_prepare()` can resolve account
   endpoints or write a `PREPARED` submission. Preflight independently reads the
   authoritative persisted snapshot, signed wrapper, registry-pinned adapter
   manifest and current economic-effect fence. The final `admit(request, at)`
   re-verifies the fully built request and safety fence. Invalid or missing
   preflight is fail-closed; simulated pilot behavior remains explicit and intact.

2. **Remove offline-guessable fingerprints.** `EncryptedSecretRecord` and
   `PostgresEncryptedSecretStore` no longer compute or store
   `plaintext_sha256` for account endpoints, contact destinations or provider
   credentials. Forward-only migration `0014` drops the legacy column. The
   AES-256-GCM encrypted envelope already authenticates its ciphertext and AAD;
   no new plaintext-derived digest is required. Migration `0007` is unchanged.

3. **Bound sandbox metric dimensions.** `MetricsRegistry` now accepts only the
   existing named sandbox counters and their exact low-cardinality label sets.
   Only the frozen synthetic pilot providers `BANK-KE` and `MPESA-KE` are
   allowed; outcome, scenario and effect-type values are enumerated. A configurable
   series cap rejects unbounded metric growth. No UTT/RTT, identity, account,
   or callback values may be inserted into label dimensions. This registry is
   for the synthetic pilot, not the future partner analytics product.

4. **Redact worker exceptions.** Worker retry records and supervisor status
   retain only the exception class name; an exception message originating from
   a provider or callback may contain sensitive financial data or credentials.

## Invariants retained

- UTT, RTT, accepted commercial terms, route-scoring evidence and canonical
  wrapper bytes/signatures are unchanged.
- The existing unknown-outcome no-replay behavior remains in force.
- Production institutional dispatch modes are still rejected.
- Historical migrations `0001`–`0013` stay byte-for-byte unchanged.
- Failed preflight may not decrypt account endpoints or create a prepared
  provider submission.

## Unresolved security gates

- **Not a durable permit.** `preflight` and `admit` are checks, not an atomic
  database-backed reservation. Another worker or a provider callback may change
  economic state between checks. Live deployment requires durable fencing,
  transaction isolation and crash/concurrency testing.
- Live PostgreSQL migration `0014` has not been exercised in this development
  environment; integration test added but skipped without a disposable DSN.
- Dropping a PostgreSQL column does not guarantee physical erasure from old
  pages, WAL, snapshots, replicas, exports or backups. Review retention,
  re-encryption and secure backup lifecycle separately.
- Existing signed request SHA-256 digests, raw callback JSON, UTT metadata and
  immutable audit records still require their own sensitivity review.
- Production DB roles/row-level security, encryption keys in managed KMS/HSM,
  security logging, IAM, provider certificate validation, environment isolation,
  independent review and incident response remain separate required gates.

## Verification

- Entire Python suite with the new regression tests.
- Static convergence and secret checks on a canonical root-only copy.
- Disposable PostgreSQL clean-install + 0013→0014 upgrade tests in CI.
- Denied/expired wrapper, adapter mismatch, fence mismatch, repeated dispatch,
  concurrent workers and unknown provider-outcome drills before external traffic.
