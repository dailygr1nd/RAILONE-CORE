# ADR-017: Immutable, deterministic RouteDecisionRecord at plan birth

- Status: Proposed for RailOne v0.16.0 Alpha Phase 2
- Scope: Initial execution-plan decisions; not yet route mutation/re-scoring decisions
- Depends on: ADR-004, ADR-016, RO-DOC-ARCH-002 and RO-DOC-RTT-006
- Migration: `0012_immutable_route_decision_records.sql` (additive after 0011)

## Context

The v0.15 scorer ranks route candidates using deterministic integer basis-point
scores. An ExecutionPlan stores eligible ranked routes, but does not preserve
all excluded candidates or a separately content-addressed account of the
inputs, policy, and decision. This weakens independent reconstruction of *why*
a specific route was chosen.

## Decision

For each **new** plan created by `ExecutionPlanningService.build_plan`:

1. Validate the persisted UTT and rank using the existing scorer.
2. Build an immutable canonical `RouteDecisionRecord` containing the exact
   UTT digest, plan ID, policy ID, policy-weight values, scoring-algorithm
   version, UTC decision time, ordered candidate snapshots, granular exclusion
   reasons, ranked routes, and the top selected route.
3. Preserve microsecond timestamps for the replay inputs, without changing
   the existing `RouteCandidate.to_payload()` historical representation.
4. Compute a SHA-256 digest over a domain-separated canonical JSON body.
5. Persist the plan and decision in the **same database transaction**.
6. A repeated same-UTT plan request may return its existing plan only if both
   plan identity and the entire decision record agree. Different decisions for
   one UTT fail closed and never rewrite the original record.
7. The in-memory store follows the same atomicity and immutability rules.

The stored record supports independent replay: reconstitute the original
candidates and scoring weights, re-evaluate exclusion reasons, re-rank, and
compare the results to persisted evidence. A digest alone is **not** sufficient
for verification.

## Non-changes and safety boundaries

- UTT creation, signatures and commercial terms do not change.
- RTT creation, fee ownership, retry/fencing and unknown-outcome policy do not change.
- Existing immutable ExecutionPlan rank snapshots and plan identifiers remain
  unchanged.
- Hashes are **integrity identifiers, not signatures**: parties with full
  database write access can recompute hashes. Authenticity and independently
  anchored evidence require a separately designed signing and audit control.
- Decision records are **not dispatch permits** or evidence of external
  settlement. No adapters or institutions may treat them as authorization.
- No backfill is performed for plans created before migration 0012. The new
  planner always creates both records; legacy plans remain operable under the
  existing pilot semantics until a separately reviewed compatibility policy.
- Changing a scorer algorithm or component normalization requires a new
  `scoring_algorithm` version and its own replay verifier. Never silently
  re-interpret old scores.

## Next stages

1. Verify migration 0012 and atomic rollback on disposable PostgreSQL.
2. Introduce append-only **route mutation** decision records with parent
   decision hashes, controlled re-scoring reasons and telemetry changes.
3. Bind signed dispatch permits and adapter selection to verified decision
   evidence, in a separate reviewed change after migration validation.
4. Maintain fail-closed unknown-outcome rules; granular fencing is a distinct
   safety project and is not authorized by this ADR.

## Acceptance gates

- Equal inputs and decision time yield identical record regardless of
  candidate enumeration order.
- Exclusion and rank evidence is identical on independent replay.
- Recomputed digest cannot conceal a changed rank or policy outcome.
- Same-UTT conflicting decisions are rejected without modifying plan or record.
- Plan and decision commit atomically, including crash/error paths.
- Existing 177-test v0.16 Alpha baseline still passes, with new tests added.
- Migration remains append-only and checksum-locked. No old migrations altered.
