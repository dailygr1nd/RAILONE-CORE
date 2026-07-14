# ADR-005: Continuity Identity and Transaction-History Projections

- Status: Accepted for pilot baseline
- Date: 2026-07-14
- Depends on: ADR-002, ADR-003, ADR-004

## Current

Before this step, RailOne could derive a stable 160-bit continuity UID from a
verified institutional subject using a versioned keyed digest. RIG, RIO, and
the initial RIV were represented as immutable Python records, and raw provider
subject references were not stored in identity continuity objects.

That baseline was cryptographically functional but operationally incomplete.
It did not support lookup by continuity UID, append later RIVs, retain a full
trust-revision history, or query accepted transactions through a continuity
identity.

## Decision

### Identity sections

RailOne identity uses three separate persistence concerns:

- **RIG** is immutable genesis and provenance. It is append-only and cannot be
  updated or deleted.
- **RIO** is the stable public continuity object. Its RailOne ID, continuity
  UID, RIG link, corridor, and creation time never change. Its active RIV
  pointer and status form a version-guarded current projection.
- **RIV** is append-only mutable history. A trust-tier, status, or verification
  change creates the next revision; it never rewrites an earlier revision.

The phrase "mutable identity" therefore means mutation by new versioned facts,
not in-place editing of identity history.

Each revision requires a valid institutional Ed25519 identity attestation. One
attestation cannot authorize more than one RIV. A revoked identity cannot
transition back to another state through the normal revision service.

### UTT and identity relationship

The UTT remains the canonical protocol transaction identity. A continuity UID
does not own or contain transactions. Instead, RailOne creates an immutable,
derived transaction projection linking a persisted signed UTT to its subjects.

For a P2P transaction, known sender and receiver continuity UIDs may be linked
with roles such as `PAYER`, `BENEFICIARY`, or `AUTHORIZER`. A continuity UID in
a UTT must resolve to a known RailOne identity before it can enter the
projection.

Commercial contexts retain their native actor boundaries:

- `merchant_id` for merchants;
- `branch_id` for branches; and
- `partner_id` for partners.

RailOne must not fabricate a human continuity UID for a merchant, branch,
partner, supplier, or other commercial actor. A merchant-context UTT may link a
real continuity UID only when a separately identified human authorizer is
actually present in the accepted origin context.

### Transaction reads

Transaction history may be resolved by:

- an exact `utt_id`; or
- a continuity UID, returning every indexed UTT for which that identity is a
  participant.

The read projection exposes transaction summary fields but does not copy raw
provider subjects or payer/beneficiary account references. It is not a custody
ledger, balance ledger, or source of settlement truth.

Subject-scoped principals may read only transactions linked to their own
continuity UID or authorized commercial scopes. A privileged
`railone.transactions.read:any` query requires an explicit access reason. Both
allowed and denied reads are appended to the access audit.

### Persistence

The SQL migration establishes:

- immutable identity-genesis rows;
- stable identity projections with optimistic versions;
- append-only identity revisions;
- immutable accepted-UTT records;
- immutable UTT transaction projections and subject links; and
- append-only transaction-access audit.

Redis is not authoritative for identity, UTTs, subject links, or access audit.

## Interpretation

After this step, the domain implementation can answer "show this UTT" and
"show the UTTs linked to this ContUID" with permission checks and access audit.
It also proves that mutable identity metadata can evolve without changing the
RIG, RailOne ID, or continuity UID.

This is a functional domain and persistence contract, not a claim that a live
PostgreSQL adapter or production identity provider has been deployed.

## Roadmap

Before live-value pilot traffic, RailOne still needs:

1. a PostgreSQL repository adapter executing this schema transactionally;
2. authenticated API handlers that derive read scope from verified tokens;
3. transactional outbox and signed projection events;
4. retention, regulatory access, and erasure-policy review;
5. production HSM or isolated continuity-derivation service; and
6. load, concurrency, migration, backup, and recovery tests.
