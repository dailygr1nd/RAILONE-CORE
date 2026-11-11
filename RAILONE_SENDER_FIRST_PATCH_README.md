# RailOne v0.16 — Corrected Sender-First ETK-S → ETK-R → UTT → RTT

**Status:** Proposed sandbox patch, not a GitHub commit or a live-money certification.

**IMPORTANT: This patch REPLACES, and must not be stacked on, the previously supplied `RailOne_v0.16_receiver_first_security.patch`.** It is generated against the original uploaded v0.16 Repomix snapshot, not against that earlier patch.

## Correct flow

1. RailOne produces a signed, expiring quote that commits to the sender, recipient, amounts, currencies, opaque account bindings, and economic terms.
2. The sender independently signs **ETK-S v3**, committing to the entire quote before any ETK-R exists.
3. The receiver verifies that ETK-S and independently signs **ETK-R v3**, containing the original `etk_s_id` and ETK-S payload digest.
4. RailOne validates the signing principals, both signatures, full quote commitments, authorization times and expirations. Only then does it atomically persist the immutable **UTT v3** and both ETK envelopes.
5. Planning, RTT creation, and strict institutional sandbox admission re-validate the bilateral chain. The RTT is dispatched only after existing admission and economic-effect fencing.
6. Unknown provider outcomes remain fenced; no blind redispatch is authorized.

**Version separation:** v3 identifies this sender-first chain. The discarded receiver-first v2 patch has different signing semantics; existing v2 artifacts must not be interpreted as v3. Legacy v1 remains only for explicit regression compatibility, not strict institutional dispatch.

## Files

- `railone_authority/bilateral.py`: ETK-S issuance/verification precedes ETK-R acceptance.
- `railone_contracts/acceptance_service.py`: sender verification then receiver acceptance; v3 immutable UTT.
- `railone_execution/service.py`: checks the v3 bilateral chain at plan/RTT boundaries and rejects superseded v2.
- `railone_postgres/dispatch_snapshot.py` and `railone_sandbox/deployment.py`: strict `require_sender_first=True` sandbox gateway; refuses older authorization.
- Institutional admission: recomputes full provider-request digest to detect beneficiary substitution before economic-fence reservation.
- Migration `0016_institution_security_audit.sql`: redacted rejection audit; no raw account endpoints, secrets, or payloads.
- `docs/ADR-023-sender-first-bilateral-and-compromise-harness.md`: flow, threat tests, and disposable PostgreSQL instructions.
- `scripts/run_compromised_institution_harness.py`: 19 structured synthetic security scenarios.

## Apply on Windows PowerShell

Use a **clean checkout matching the original uploaded v0.16 snapshot**:

```powershell
git switch -c feat/sender-first-bilateral-v3
git apply --check .\RailOne_v0.16_sender_first_security.patch
git apply .\RailOne_v0.16_sender_first_security.patch
python -m pip install -e ".[pilot]"
python scripts/run_compromised_institution_harness.py
python run_tests.py
```

If the earlier receiver-first patch was applied to an uncommitted, otherwise unmodified tree, reverse it first using the actual path of the earlier patch:

```powershell
git apply --check -R .\RailOne_v0.16_receiver_first_security.patch
git apply -R .\RailOne_v0.16_receiver_first_security.patch
```

**Do not blindly reverse** an already committed/mutated branch; review the changes or create a clean v0.16 branch instead.

## Local validation

- Full Python suite: **273 tests run, 263 passed, 10 skipped, 0 failed**.
- Synthetic compromised-institution JSONL harness: **19/19 passed**.
- Repository convergence: **passed** after removing local generated `__pycache__` artifacts.
- Repository secret check: **passed**.
- Patch application checked against reconstructed original v0.16 source files.
- **Live PostgreSQL remains unverified locally**; tests requiring the disposable database were skipped.

## Disposable PostgreSQL gate (destructive to the specified disposable database)

```powershell
docker run -d --name railone-pg-disposable `
  -e POSTGRES_DB=railone_test `
  -e POSTGRES_USER=railone_test `
  -e POSTGRES_PASSWORD=railone_test `
  -p 55432:5432 postgres:17-alpine
$env:RAILONE_TEST_DATABASE_URL = "postgresql://railone_test:railone_test@localhost:55432/railone_test"
$env:RAILONE_ALLOW_TEST_SCHEMA_RESET = "1"
$env:RAILONE_REQUIRE_LIVE_POSTGRES = "1"
python run_tests.py
```

If the container already exists, use `docker start railone-pg-disposable` instead. The integration test drops test `railone` / `railone_bank` schemas; **never run these settings against production or a shared database**.

## Remaining integration gates

Authenticated client/API endpoints for sender issuance and receiver consent; delegated signer/KMS/HSM policy; verified institution capability and contractual authorization; live PostgreSQL, failure/concurrency/recovery drills; external tamper-resistant audit replication and incident response. This is a sandbox hardening patch, not certification for production payment traffic.
