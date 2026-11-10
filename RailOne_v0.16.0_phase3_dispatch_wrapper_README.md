# RailOne v0.16.0 Alpha — Phase 3 Signed Institution Dispatch Wrapper

**Status:** Additive implementation candidate. **Not production/live-money ready.** The signed wrapper is **NOT** a dispatch permit. The legacy `ProviderSubmissionCoordinator` and `InstitutionAdapterBridge` are not yet forced through this wrapper. That enforcement requires a separate trusted admission/dispatch gateway.

**Source baseline:** The July 2026 v0.15.0 Repomix snapshot with the validated v0.15.1 reproducibility fixes, currency registry migration 0011 and Phase 2 RouteDecisionRecord migration 0012 applied. This matches the previously delivered Phase 2 patch, not necessarily any newer unshared commits.

## Files

Modified:
- `railone_crypto/signature_service.py` — new domain-separated Ed25519 artifact kind
- `railone_institutions/__init__.py` — exports wrapper types and store
- `railone_postgres/__init__.py` — exports SQL repository
- `scripts/check_repository_convergence.py` — migration 0013 in checksum-locked chain
- `tests/test_postgres_live.py` — migration/append-only trigger validation when a disposable database is configured

New:
- `railone_institutions/wrapper.py` — immutable canonical payload, schema, signed validation and trusted snapshot comparison
- `railone_institutions/wrapper_store.py` — verified append-only in-memory test store
- `railone_postgres/dispatch_wrappers.py` — signed-envelope PostgreSQL persistence; requires independently provided expected core state
- `migrations/0013_signed_institution_dispatch_wrappers.sql` — append-only table and foreign keys
- `tests/test_institution_dispatch_wrapper.py` — schema, signing, tamper, replay and immutability tests
- `docs/ADR-018-signed-institution-dispatch-wrapper.md` — decision, trust boundaries and unresolved gates
- `docs/fixtures/institution-dispatch-wrapper-synthetic-v1.json` — UNSIGNED synthetic Uganda→Tanzania example

## Apply on Windows PowerShell

From the RailOne repository root:

```powershell
# Phase 2 code and migration 0012 MUST already be present on this branch.
git switch feat/v0.16-route-decision-evidence
git status --short
# If the feature branch does not exist, finish Phase 2 first; do not base this on Phase 1.
git switch -c feat/v0.16-signed-dispatch-wrapper

# Copy RailOne_v0.16.0_phase3_signed_dispatch_wrapper_0013.patch into the root.
git apply --check .\RailOne_v0.16.0_phase3_signed_dispatch_wrapper_0013.patch
# ONLY if the check succeeds:
git apply .\RailOne_v0.16.0_phase3_signed_dispatch_wrapper_0013.patch

$env:PYTHONDONTWRITEBYTECODE = "1"
python -m unittest tests.test_institution_dispatch_wrapper -v
python run_tests.py
python scripts/check_repository_convergence.py
python scripts/check_no_secrets.py
git diff --check
git diff --stat
```

When all checks pass, stage ONLY the implementation files (do not stage downloaded ZIP/patch files):

```powershell
git add railone_crypto/signature_service.py railone_institutions/__init__.py railone_institutions/wrapper.py railone_institutions/wrapper_store.py
git add railone_postgres/__init__.py railone_postgres/dispatch_wrappers.py
git add migrations/0013_signed_institution_dispatch_wrappers.sql scripts/check_repository_convergence.py
git add tests/test_institution_dispatch_wrapper.py tests/test_postgres_live.py
git add docs/ADR-018-signed-institution-dispatch-wrapper.md docs/fixtures/institution-dispatch-wrapper-synthetic-v1.json
git diff --cached --check
git diff --cached --stat
git commit -m "feat(institutions): add signed canonical dispatch wrapper"
git push -u origin feat/v0.16-signed-dispatch-wrapper
```

If `git switch -c` reports an existing branch, switch to it after checking for uncommitted changes. If `git apply --check` reports already-existing files or changed context, do **not** force it. Compare with `git status --short` and run `git apply --reverse --check` to determine whether it is already present.

## Validation in packaging environment

- Full suite: **207 discovered, 204 passed, 3 skipped**, no failures/errors.
- Phase 3 adds **17 unit tests** over the Phase 2 baseline of 190.
- Repository convergence and secret checks passed after removing generated caches.
- Source compiled successfully.
- Clean application to a reconstructed Phase 2 source baseline verified.
- **PostgreSQL migration 0013 has not been run against an actual PostgreSQL server.** An integration test now asserts its table and immutability trigger when the disposable DB gate runs; approval is pending real execution.

## Non-goals and next security gate

The wrapper binds an authenticated envelope to an **authoritative snapshot supplied by trusted RailOne Core**. Code cannot infer from a caller-supplied snapshot that the core really checked the quote, UTT, RTT, ETKs, decision record, adapter certificate, account references, economic-effect fence and any licensing grant. The new wrapper does not yet connect to the actual dispatch coordinator or enforce a license. Its signature is NOT sufficient to authorize sending funds. The next implementation must load the snapshot from authenticated stores and require the verified wrapper plus an atomic dispatch permit at every provider dispatch path, without weakening unknown-outcome safety.

Your institution-facing adapter SDK remains a subsequent package; do not distribute this internal source tree as the final partner SDK.
