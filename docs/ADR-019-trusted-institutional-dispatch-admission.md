# ADR-019 — Trusted Institutional Dispatch Admission (Phase 4)

- **Status:** Proposed, sandbox integration candidate only
- **Predecessor:** ADR-018 and migrations through `0013`
- **No new database migration:** uses existing signed wrapper, adapter registry, UTT/RTT, and signed outbox storage

## Decision

Introduce a mandatory admission check when `ProviderSubmissionCoordinator` is
explicitly configured for `INSTITUTIONAL_SANDBOX` mode. In this mode:

1. Caller-supplied provider adapters are rejected; the gateway resolves an exact
   signed adapter version from the protected institution registry.
2. The signed canonical wrapper must be persisted and valid within its short
   lifetime; verification uses a trusted snapshot loaded from independent RailOne
   source-of-truth stores rather than an API-supplied snapshot.
3. Wrapper request digest, provider, UTT, RTT, idempotency key, currencies and
   minor-unit amounts must match the actual prepared provider request.
4. The signed capability manifest must remain active, unchanged, version-pinned,
   and eligible for the declared sandbox or pilot environment.
5. An independent *economic-effect fence reader* must approve each specific
   attempt and epoch based on authoritative, durable state. A cancellation
   token or wrapper `release_evidence_ref` alone is NOT proof of cancellation.
6. The gate runs before setting the provider submission to `DISPATCHING`.
   Existing CAS/outbox behavior and unknown-outcome replay blocks remain active.
7. Direct `prepare()` access to provider-ready account references is blocked in
   institutional mode. `SIMULATED_PILOT` retains existing interfaces to avoid
   breaking historic tests and synthetic demos.

## Explicit limitations and nonclaims

- **Not enabled for live funds.** The coordinator rejects production/live mode.
- The trustworthiness of snapshot/fence readers is critical. Their durable,
  fail-closed implementations and security review are not delivered by Phase 4.
- No distributed reservation or atomic dispatch authorization row is introduced;
  additional transaction-level fencing and crash recovery are required before
  a real institutional pilot. The adapter `submit()` call remains outside the
  SQL transaction; it can have an unknown outcome.
- InstitutionLicenseGrant and commercial entitlements remain Phase 5. Pilot
  mode does not silently grant a license.
- Caller-supplied `ProviderAdapter` remains available **only** in the explicit
  simulated-pilot mode. Operators MUST NOT treat that default as production-safe.
- Adapter conformance does not prove external institution approval.

## Acceptance tests

Valid signed wrapper + verified manifest + trusted fence permits a reference
sandbox adapter. Missing or expired wrapper, changed amount, wrong manifest
hash, unsupported corridor or route, stale fence, and caller-supplied adapter
must fail before provider effect. Unknown outcomes must still block blind retry.

## Next implementation gate

Wire authoritative snapshot and fence readers to PostgreSQL with transaction
isolation and audit evidence. Strengthen dispatch reservation/CAS and pass live
PostgreSQL concurrency, recovery, and late-settlement tests. Add license checks
before any controlled live-use consideration.
