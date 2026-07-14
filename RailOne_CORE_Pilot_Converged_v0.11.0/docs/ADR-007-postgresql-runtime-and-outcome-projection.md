# ADR-007: PostgreSQL Runtime and Exactly-Once Outcome Projection

**Status:** Accepted for the controlled pilot  
**Date:** 2026-07-14

## Decision

PostgreSQL is the authoritative operational store for RailOne identity
continuity, accepted UTT contracts, execution plans, RTT attempts, provider
submissions, transaction-history projections, signed outbox events, and
provider-progress projections.

Repository operations own short transactions. Multi-record domain transitions
must commit atomically. Version columns provide compare-and-swap concurrency;
outbox workers claim work using `FOR UPDATE SKIP LOCKED` and expiring leases.
Redis and brokers may accelerate coordination but never replace PostgreSQL
truth.

The immutable ExecutionPlan birth snapshot and its evolving runtime state are
stored separately. `plan_snapshot` cannot change. `plan_state` contains
remaining routes, failure history, and previous-route lineage and changes only
with the plan version.

Signed provider events are verified before projection. The projection inbox
deduplicates by consumer and event ID, binds each event ID to its signed payload
hash, and rejects conflicting replay. Later events may advance a provider
projection; delayed older events are consumed but cannot regress it.

`PROVIDER_SUBMISSION_ACCEPTED` projects as `ACCEPTED_FOR_PROCESSING`. It is not
settlement success. Only later verified callback or reconciliation evidence may
finalize an RTT and UTT.

## Migration semantics

- Migrations are ordered by four-digit version.
- Applied bytes are SHA-256 locked. An edited applied migration is rejected.
- A PostgreSQL advisory lock permits one migrator at a time.
- Each migration and its registry entry commit together.
- Schema `0003` adds `plan_state`, the projection inbox, and provider outcome
  read model.

## Consequences

Step 07 supplies production-shaped adapters but does not itself prove a live
PostgreSQL deployment. Before the pilot release gate, all migrations and
repository concurrency cases must run against the pilot PostgreSQL version,
including clean install, Step 06 upgrade, crash, duplicate, and connection-loss
tests.

Authenticated APIs are Step 08. Provider sandbox and callback normalization are
Step 09. No live funds may move until those steps and the release gates pass.
