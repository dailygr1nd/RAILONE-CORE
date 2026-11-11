# RailOne v0.16 sender-first PostgreSQL integration hotfix

**Applies only AFTER the v0.16 sender-first security patch.** Do not apply this
hotfix directly to the original v0.16 snapshot or to the superseded receiver-first patch.

## What the four live PostgreSQL errors mean

1. `IdempotencyConflictError` in `test_bilateral_postgres_live.py` was the
   correct rejection of a reused idempotency key. The malicious changed-quote
   test now uses a new key to reach its intended `SENDER_QUOTE_BINDING_MISMATCH`
   assertion. It separately confirms key reuse still raises a conflict.
2. The three institutional live dispatch tests used the previous synthetic
   ETK-S + post-UTT ETK-R fixture. The strict institutional dispatcher correctly
   denied that legacy UTT. The live fixture now generates independently signed
   payer ETK-S and receiver ETK-R **before accepting the UTT**, persists them
   atomically and asserts the v3 chain. The `SENDER_FIRST_BILATERAL_V3_REQUIRED`
   safety gate remains enabled.

## Changed files

- `tests/test_bilateral_postgres_live.py`
- `tests/test_provider_operations.py`
- `tests/institutional_live_support.py`

All changes are to test fixtures/integration tests; no production dispatch
authorization rule, PostgreSQL migration, or engine rule was relaxed.

## Apply on Windows PowerShell

Use a clean branch containing the sender-first patch, not both old patches.
Copy `RailOne_v0.16_sender_first_postgres_test_hotfix.patch` to the repository root:

```powershell
git status --short
git apply --check .\RailOne_v0.16_sender_first_postgres_test_hotfix.patch
git apply .\RailOne_v0.16_sender_first_postgres_test_hotfix.patch
```

With the disposable PostgreSQL container running:

```powershell
$env:RAILONE_TEST_DATABASE_URL = "postgresql://railone_test:railone_test@localhost:55432/railone_test"
$env:RAILONE_ALLOW_TEST_SCHEMA_RESET = "1"
$env:RAILONE_REQUIRE_LIVE_POSTGRES = "1"
$env:PYTHONDONTWRITEBYTECODE = "1"
python run_tests.py
```

**Warning:** The suite DROPS and recreates the `railone` and `railone_bank`
schemas. Never point these variables at a non-disposable database.

For focused reruns:

```powershell
python -m unittest -v tests.test_bilateral_postgres_live tests.test_postgres_live
```

## Validation performed in this environment

- `python run_tests.py`: **274 tests, 264 passed, 10 skipped**.
- New in-memory regression explicitly verifies the independently signed v3
  ETK-S -> ETK-R -> UTT -> RTT institutional fixture.
- Repository convergence check: passed (after clearing generated pycache).
- Secret check: passed.
- Patch `git apply --check` and byte-for-byte changed-file equality: passed.

**Not yet validated here:** live PostgreSQL tests; no PostgreSQL instance is
available in this execution environment. The user must rerun on the disposable
container and share any additional traceback.
