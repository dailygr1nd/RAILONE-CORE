# RailOne v0.16 — Security Hardening Slice A (ADR-020)

Base: uploaded v0.16 snapshot with migrations 0011, 0012, 0013 and Phase 4 admission.
This is a forward-only additive patch plus migration 0014; **not** permission to deploy live funds.

## Changes

- Phase 4 institutional sandbox `preflight()` checks before protected endpoint resolution and prepared submission write.
- Existing `admit()` still validates full signed request against trusted authority and fence.
- Remove unkeyed plaintext SHA-256 copies of account/contact/credential values from encrypted secret records.
- Migration `0014_drop_plaintext_secret_fingerprints.sql` drops the legacy DB column.
- Bound synthetic sandbox metrics to fixed labels and approved values.
- Remove provider exception text from persisted worker errors.
- Add ADR-020, regression tests and disposable-PostgreSQL integration test.

## Apply (PowerShell, from repository root)

```
git switch feat/v0.16-institutional-admission
git pull --ff-only origin feat/v0.16-institutional-admission
git status --short
git switch -c fix/v0.16-security-boundaries
git apply --check .\RailOne_v0.16_security_phase5.patch
git apply .\RailOne_v0.16_security_phase5.patch
$env:PYTHONDONTWRITEBYTECODE = "1"
python run_tests.py
python scripts/check_repository_convergence.py
python scripts/check_no_secrets.py
git diff --check
```

If the branch already exists, switch to it. If `git apply --check` fails, STOP;
do not force changes. `git status --short` should be clean before applying.
If the root contains historical `step_*` or `source/` directories, the checker
may fail independently of this patch: clean up tracked duplicates in a separate
reviewed commit, do not blindly delete work.

## Expected local test results

Baseline snapshot: 222 tests, 219 passed and three PostgreSQL skips.
After patch: **232 tests, 228 passed and four skips** in the reconstructed source.
The extra skipped test checks the new encrypted-vault schema against PostgreSQL.
The precise count may differ if your local branch contains additional tests.

## Validate migration 0014 against disposable PostgreSQL

CI has a PostgreSQL 17 service and sets `RAILONE_TEST_DATABASE_URL`,
`RAILONE_ALLOW_TEST_SCHEMA_RESET=1` and `RAILONE_REQUIRE_LIVE_POSTGRES=1`.
Ensure the full suite runs without skips in CI. The live database test wipes
`railone` schema; never point it at a partner or production database.
Apply migrations only through the repository's checksum-aware MigrationRunner.

## Commit

```
git add railone_institutions/admission.py railone_operations/service.py
git add railone_security/ railone_postgres/security.py railone_sandbox/
git add migrations/0014_drop_plaintext_secret_fingerprints.sql
git add docs/ADR-020-dispatch-confidentiality-and-telemetry-hardening.md
git add scripts/check_repository_convergence.py tests/
git diff --cached --check
git diff --cached --stat
git commit -m "security: protect dispatch preflight and sensitive metadata"
git push -u origin fix/v0.16-security-boundaries
```

Do not merge until CI and disposable PostgreSQL pass. For upgrade planning,
note that `DROP COLUMN` does not erase earlier WAL, backups or exports.
