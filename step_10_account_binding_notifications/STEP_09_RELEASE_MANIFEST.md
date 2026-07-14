# Step 09 release manifest

- Build date: July 14, 2026
- Package version: 0.9.0
- Frozen provider: `MPESA-KE`
- Corridor: Kenya domestic
- Currency: KES to KES
- Provider operation: Daraja B2C sandbox
- Custody model: non-custodial intention execution
- Signature baseline: Ed25519 for RailOne-owned signed artifacts
- Test discovery: 98
- Runnable tests passed: 91
- Expected environment skips: 7

The skips are four optional FastAPI transport checks and three destructive live
PostgreSQL checks. They are release gates to run in the target environment, not
evidence of failure and not permission to claim that those gates have passed.

## Included Step 09 controls

- non-idempotent provider recovery blocks a second B2C call;
- immediate provider acceptance is not execution finality;
- trusted-ingress HMAC over the exact raw callback body;
- callback reference, amount, transaction ID, and receipt correlation;
- sanitized, replay-conflict-detecting callback inbox;
- timeout-to-reconciliation and late-result resolution;
- PostgreSQL provider correlation context and RTT transition guard; and
- sandbox setup, failure-drill, and no-go runbook.

## Outstanding before sandbox traffic

- confirm B2C entitlement, endpoint version, and callback fields in the
  authenticated Daraja application;
- pass all seven environment-dependent checks;
- deploy and test the callback gateway controls;
- wire a secret manager instead of long-lived process environment secrets; and
- execute concurrency, worker-crash, backup/restore, and rollback drills.
