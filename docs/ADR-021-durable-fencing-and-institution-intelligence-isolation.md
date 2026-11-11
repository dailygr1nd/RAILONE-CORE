# ADR-021 — Durable Economic Fencing and Bank Intelligence Isolation

**Status:** Sandbox integration candidate. **Requires disposable PostgreSQL test, external proof validation, and deployment review before use.**

## Security invariants

1. The accepted UTT is the economic-effect boundary; one UTT permits at most one potentially effective dispatch at a time. One RTT is only an operational attempt, not a new charge.
2. Reserve a UTT hold under a PostgreSQL row lock *before* calling the institution. A reserved RTT is never automatically re-dispatched: crash, timeout, expired worker lease, provider acceptance, and `UNKNOWN` all retain the hold.
3. Per-RTT operational state is persisted separately from the UTT economic hold. One uncertain RTT does not block unrelated UTTs. The network does not have a global mutex.
4. An independent, purpose-separated Ed25519-signed `railone.no_effect_evidence` from an explicitly trusted settlement/reconciliation key is required to release a held UTT. The issuing service must verify authenticated provider/bank evidence and the absence of settlement before signing. A syntactically valid signature is not proof the original bank outcome was examined.
5. Release advances the epoch. The next signed wrapper must pin the new epoch and exact release evidence ID; an older wrapper is invalid. Definitive settlement evidence finalizes the fence; no replay.
6. An accepted-for-processing provider response is not settlement finality. Provider `REJECTED` is not an automatic no-effect release. A late contradictory settlement is an incident requiring operator escalation, never automatic retry.
7. Legacy `SIMULATED_PILOT` behavior remains test-only; production mode is still rejected. Signatures alone do not grant live-bank execution authority.
8. The protected `railone` schema holds raw route snapshots, alternate routes, costs, and signed evidence. Bank-specific PostgreSQL logins only access `railone_bank.metrics`, a security-barrier view backed by RLS and a server-side `SESSION_USER` map. Never rely on an API-supplied bank ID or writable session setting to determine access.
9. Bank analytics is a reviewed publication workflow, not a dynamic query over raw routing tables. Only four allowlisted own-bank metrics are accepted; publication windows must span at least one day and cohorts include at least 20 samples. No raw UTTs, RTTs, counterparties, alternate routes, pricing or competitor performance is published.

## Atomic reservation and recovery

`PostgresEconomicEffectFence.reserve_dispatch` locks the existing `accepted_utts` row, validates the current active RTT and prepared request hash, and creates both UTT/RTT fence records in one transaction. Concurrent workers for the same UTT serialize. Another UTT is unaffected. A second reservation, even for the same RTT, is denied rather than risking a duplicate effect. The adapter call remains outside SQL transaction; its outcome is recorded afterward and **does not clear** the hold. A crash between reservation and the provider request may require manual investigation, deliberately prioritizing safety over liveness.

`release_verified_no_effect` verifies the trusted signature, checks RTT/UTT/provider linkage and absence of persisted settlement evidence, stores the signed attestation, advances the epoch and releases the operational RTT in one transaction. This is only as strong as the trusted external reconciliation/signing pipeline and consistency of all settlement sources. No application-level release endpoint should be exposed until that pipeline is certified.

## Bank access provisioning

Create a separate PostgreSQL LOGIN per bank in an isolated deployment through an administrator. Example placeholders only (never commit passwords):

```sql
-- Run as a privileged DB administrator after migration 0015.
CREATE ROLE railone_bank_reader NOLOGIN;
-- Separate analytics publisher LOGIN, credentials issued through a secrets manager.
-- CREATE ROLE railone_analytics_publisher LOGIN PASSWORD '<provisioned-out-of-band>';
-- GRANT USAGE ON SCHEMA railone TO railone_analytics_publisher;
-- GRANT INSERT ON railone.bank_analytics_publications TO railone_analytics_publisher;
-- GRANT INSERT ON railone.bank_analytics_withdrawals TO railone_analytics_publisher;
GRANT USAGE ON SCHEMA railone_bank TO railone_bank_reader;
GRANT EXECUTE ON FUNCTION railone_bank.current_institution_id()
    TO railone_bank_reader;
GRANT SELECT ON railone_bank.metrics TO railone_bank_reader;

-- Individual bank login and credentials provisioned through secrets management.
-- CREATE ROLE bank_example_login LOGIN PASSWORD '<provided-out-of-band>';
-- GRANT railone_bank_reader TO bank_example_login;
-- INSERT INTO railone.bank_analytics_principals(login_role,institution_id,enabled)
-- VALUES ('bank_example_login','BANK-TZ-ALPHA',true);
```

Do not grant `USAGE ON SCHEMA railone` or `SELECT` on the raw operational tables to the reader role. Validate two distinct bank logins; test that A cannot read B even after `SET ROLE`, and that an unmapped login receives no rows. `SESSION_USER` is the authenticated login; `SET ROLE` changes `CURRENT_USER` but not `SESSION_USER`. Use **session pooling keyed by bank login** or fresh connections. Never share an authenticated bank DB login between customers.

## Required release gates

- Execute migrations `0001`–`0015` on a disposable PostgreSQL 17 instance; verify checksum idempotency and tenant access with distinct real LOGIN roles.
- Race two workers for the same UTT (only one reserve succeeds), two different UTTs (both independent), crash immediately after reserve, duplicate/late callbacks and release-vs-settlement races.
- Build the trusted authoritative snapshot reader and prove dispatch cannot bypass the gateway through another adapter path.
- Verify the *external* signed no-effect claims against bank/provider evidence before issuance; enforce dual-control for manual exceptions, revocation and signing key rotation.
- Authenticate bank APIs with a production-grade token/mTLS gateway. Do not expose direct SQL to banks without reviewed credential and connection isolation.
- Implement purpose-specific least-privilege database roles for execution, reconciliation, analytics publishing, operational reporting, secrets and migrations; audit every grant and membership.
- Ensure analytics publication approvals are authenticated, dual-controlled where necessary, and privacy tested against inference/correlation; establish retention rules.
- Run all PostgreSQL tests with no skips and verify CI, backup/restore, disaster recovery, secret scanning and independent security assessment.

## Internal PostgreSQL sandbox dispatcher

`DeployedSandboxRuntime.institutional_dispatcher(...)` composes the coordinator,
verified registry, PostgreSQL wrapper and snapshot readers, encrypted endpoint
vault, and PostgreSQL fence. It is an internal entry point for sandbox adapters
and continuity-bound P2P UTTs. Both parties must have active continuity records
and active, matching opaque account bindings. The snapshot uses the RTT ID as
the correlation ID and the verified endpoint institution IDs as routing nodes.
Merchant and supplier actor IDs need a separately verified continuity mapping
before they can use this dispatcher.

A trusted provisioning process must supply the signed adapter manifest, one
unambiguous signed ETK-R per UTT, and the signed wrapper per RTT before dispatch.
The snapshot reader verifies both authorities, their lineage and validity
window. The wrapper signature and all independently readable anchors are
checked before endpoint resolution. The coordinator computes the request digest
after resolution and compares it with the signed digest before persisting the
request. Final admission rechecks the wrapper and reserves the fence before the
adapter call. A held fence blocks subsequent dispatch attempts.

The dispatcher does not provision ETK-Rs, issue wrappers, or certify external
no-effect evidence. The internal composition and its database queries still
require a disposable PostgreSQL integration run.
