# ADR-023 — Sender-First Bilateral Authority and Compromised-Institution Sandbox

**Status:** Proposed sandbox hardening; Python conformance validated, live PostgreSQL validation pending.

**Supersedes for P2P sandbox traffic:** legacy UTT-first / ETK-S-after-UTT issuance documented in ADR-003. **Does not supersede:** economic-effect fencing, immutable RTT birth evidence, provider-outcome reconciliation, or partner adapters.

## 1. Required P2P lifecycle

1. RailOne issues a signed, expiring, route-independent quote containing amount, sender/receiver endpoint snapshots, currency, fees, routing budget, limits, and policy.
2. The independently authenticated **sender** signs **ETK-S v3** over the **whole quote payload commitment**, including both opaque account-binding snapshots.
3. The independently authenticated **receiver** verifies ETK-S and signs **ETK-R v3** over that exact quote commitment, including ETK-S's identifier and payload digest, and an explicit ACTIVE_ACCEPTANCE assertion.
4. The accepting service verifies the quote, both separately signed authorities, signer ownership (`iss` equals actor ID), ordering, expiry, purpose and quote/endpoints. It **does not create a sender signature** from a caller-supplied key name.
5. RailOne mints and atomically persists the immutable signed **UTT v3** and both ETK envelopes, with ETK digests included in UTT's signed payload. Quote uniqueness/idempotency apply as before.
6. `ExecutionPlanningService.build_plan` and `RttAttemptService.start_next` independently re-verify ETK-S, ETK-R and the UTT commitment against the stored authorities and current key revocation state before creating an ExecutionPlan or RTT.
7. The institutional sandbox dispatch snapshot reader verifies ETK-S/ETK-R again from independently persisted authority records, together with route, identity, binding, adapter manifest and economic fence. The **strict deployed sandbox dispatcher defaults to sender-first v3 only**.
8. The institutional dispatch gateway independently hashes the complete provider request, including protected endpoint references, compares the result with the signed wrapper, then atomically reserves the economic-effect fence **before** invoking an institution adapter.
9. Provider `UNKNOWN` or timeout **does not release the hold or authorize blind redispatch**. Only valid no-effect/reconciliation evidence may release the fence.

### Why ETK-R and ETK-S do not contain a UTT ID

Both parties authorize the signed quote **before** the UTT exists. Requiring the new UTT ID in either pre-UTT signature would introduce a circular dependency. Instead, each ETK binds the quote digest; ETK-R also binds ETK-S, and the immutable UTT binds both ETK identifiers and digests. UTT/RTT lineage is subsequently protected by the signed UTT payload digest.

### Versioning

- `authority_version: 3` on ETK-S, ETK-R, and UTT identifies the sender-first chain; v2 receiver-first artifacts must never be reinterpreted as v3.
- Historical v1 acceptance remains available to existing fixtures until migration is complete, but it **must not be treated as sender-first authorization**. Strict acceptance refuses to return a previously accepted v1 P2P UTT even when the idempotency key matches.
- `DeployedSandboxRuntime.institutional_dispatcher(..., require_sender_first=True)` rejects historical v1 P2P dispatch; the only compatibility escape hatch is an explicit `False`, reserved for synthetic regression fixtures.
- `DeployedSandboxRuntime.sender_first_p2p_acceptance(...)` composes strict P2P acceptance with a durable redacted audit sink. Existing API HTTP endpoints do not automatically expose the new acceptance sequence; the client/SDK wiring still needs implementation.

## 2. Security audit

Migration `0016_institution_security_audit.sql` adds append-only `railone.institution_security_audit`. Its fields are intentionally limited to:

- `event_id`, `occurred_at`
- `event_type` (`BILATERAL_AUTH_REJECTED`, `INSTITUTION_DISPATCH_REJECTED`)
- `operation` (`ACCEPT`, `PLAN`, `RTT_CREATE`, `PREFLIGHT`, `ADMIT`)
- safe, bounded `correlation_ref`, allowlisted `reason_code`, and `DENIED` outcome.

No raw user identity, bank account, contact information, signing secrets, full ETK payloads, or raw exception messages are logged. Postgres append-only triggers prevent application-level mutation; **external immutable log replication and compromised-database-admin protection are not supplied by this patch**.

Example query after migration:

```sql
SELECT occurred_at, event_type, operation, correlation_ref, reason_code, outcome
FROM railone.institution_security_audit
ORDER BY occurred_at DESC
LIMIT 50;
```

A rejection is an audit event, **not by itself proof that an institution is compromised**. Institution-wide suspensions, capability quarantine, incident triage, regulatory notification and trust-anchor rotation need a separate governed operating policy.

## 3. Compromised-institution conformance scenarios

Run `python -m unittest -v tests.test_compromised_institution_harness` or `python scripts/run_compromised_institution_harness.py`.

Tests assert that unauthorized economic effects cannot be initiated **through the exercised boundaries**:

1. Sender-first happy path: ETK-S → ETK-R → UTT → ExecutionPlan → RTT.
2. Missing ETK-R after ETK-S (no UTT).
3. Rogue ETK-R signer (no UTT).
4. Modified ETK-R (redacted audit, no UTT).
5. ETK-R replay under a different quote (no UTT).
6. Expired receiver consent (no UTT).
7. Revoked receiver key blocks planning.
8. Tampered persisted ETK-S blocks the first RTT after planning.
9. Unauthorized route endpoint is ineligible.
10. Expired authority blocks RTT creation.
11. Admission preflight denial produces redacted audit.
12. Substituted private beneficiary endpoint fails the recomputed provider-request digest before fence reservation.
13. Unknown provider outcome does not clear an economic hold.
14. Non-idempotent crash recovery blocks duplicate adapter submission.
15. Receiver consent alone cannot mint a UTT without sender signature.
16. A validly signed ETK-S from a different owner cannot impersonate the sender.
17. ETK-R bound to a different valid ETK-S cannot authorize this sender intent.
18. ETK-R cannot be issued before ETK-S.
19. Tampered ETK-S cannot be accepted by the receiver.
20. A substituted sender ETK from another quote is rejected.

`tests/test_bilateral_postgres_live.py` also validates the atomic persistence of ETK-R and ETK-S, planning and RTT creation, and a durable rejected-acceptance audit entry against a disposable PostgreSQL instance. This test is skipped without an explicitly configured disposable database; a passing Python suite alone is not proof of database integration.

## 4. Disposable PostgreSQL execution (PowerShell / Windows + Docker)

**Destructive only to the disposable test database. Do not point these commands at production or shared environments.**

```powershell
docker run -d --name railone-pg-disposable `
  -e POSTGRES_DB=railone_test `
  -e POSTGRES_USER=railone_test `
  -e POSTGRES_PASSWORD=railone_test `
  -p 55432:5432 postgres:17-alpine

$env:RAILONE_TEST_DATABASE_URL = "postgresql://railone_test:railone_test@localhost:55432/railone_test"
$env:RAILONE_ALLOW_TEST_SCHEMA_RESET = "1"
$env:RAILONE_REQUIRE_LIVE_POSTGRES = "1"
python -m pip install -e ".[pilot]"
python run_tests.py
python scripts/run_compromised_institution_harness.py
```

If the named disposable container already exists, start it instead of creating another. CI already provides a temporary PostgreSQL service; CI must run the new live test before promoting this patch.

## 5. Scope and limitations

- This patch is an **institutional sandbox/conformance** step, not authority to send real money.
- ETK signing helpers use an injected signer; production sender and receiver signatures must come from independently authenticated, authorized principals or tightly scoped delegated institutional signers. User authentication, delegation, KMS/HSM and key rotation still require integration review.
- Existing partner-bank capability permissions, bilateral agreements and regulated settlement responsibilities remain distinct from ETK cryptographic consent.
- Legacy v1 transaction compatibility is preserved; migration of clients and fixtures to v3 is still outstanding.
- The new audit table is **not** a security information/event management platform or an external tamper-proof evidence vault.
- Route/quarantine automation, production-level load/fault injection, independent bank attestations and authorized settlement finality require separate certification.
- No live PostgreSQL test has been executed in the packaging environment if no disposable PostgreSQL instance was available. Run the gated live test before merging.
