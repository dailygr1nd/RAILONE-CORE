# Step 10 release manifest

- Build date: July 14, 2026
- Package version: 0.10.0
- Custody model: non-custodial
- UTT endpoint model: version 1
- Signature baseline: Ed25519
- Test discovery: 108
- Runnable tests passed: 101
- Expected environment skips: 7

The skips are four optional FastAPI transport checks and three destructive live
PostgreSQL checks. They remain release gates.

## Included controls

- active partner-institution eligibility;
- actor-owned debit and credit account bindings;
- immutable UTT endpoint snapshots without raw account endpoints;
- partner validation at quote issuance and before every RTT;
- source/destination institution enforcement in route eligibility;
- dispatch-time account endpoint resolver boundary;
- Ed25519-signed settlement evidence;
- exactly one sender and receiver SMS record per evidence;
- privacy-safe, deterministic, versioned SMS templates;
- uncertain non-idempotent SMS recovery blocking; and
- PostgreSQL state and immutability guards.

## Outstanding before pilot traffic

- replace in-memory account and contact resolvers with isolated encrypted
  services;
- select and certify an SMS gateway and sender identity;
- pass all seven environment-dependent checks;
- exercise migration from the previous pilot schema on a disposable database;
- run binding-revocation, callback-crash, duplicate-settlement, and SMS-worker
  concurrency drills; and
- complete privacy, retention, communications, and provider review.
