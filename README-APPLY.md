# RailOne v0.16.0 Alpha Phase 2 — Route Decision Evidence

**Source baseline:** Repomix RailOne Core v0.15.0 with the previously validated pilot reproducibility fixes and v0.16.0 Alpha Phase 1 currency registry (`0011`), matching the user-pushed Phase 1 commit `97e3f53` as far as the supplied snapshot establishes.

**Status:** Implementation candidate for review. Not live-funds ready. PostgreSQL integration is included but has **not** been executed against a live database in the packaging environment.

## Apply on Windows PowerShell

Your currency Phase 1 code must already be committed. From `RAILONE PROTOTYPE`:

```powershell
git switch feat/v0.16-currency-settlement-policy
git pull --ff-only origin feat/v0.16-currency-settlement-policy
git status --short

git switch -c feat/v0.16-route-decision-evidence
```

If the new branch exists, use `git switch feat/v0.16-route-decision-evidence` instead. Do not proceed with uncommitted unrelated changes.

Download `RailOne_v0.16.0_phase2_route_decision_0012.patch` into the repository root and run:

```powershell
git apply --check .\RailOne_v0.16.0_phase2_route_decision_0012.patch
```

Only if this check prints no errors:

```powershell
git apply .\RailOne_v0.16.0_phase2_route_decision_0012.patch
$env:PYTHONDONTWRITEBYTECODE = "1"
python run_tests.py
python scripts/check_repository_convergence.py
python scripts/check_no_secrets.py
git diff --check
git diff --stat
```

**Reference results from the prepared snapshot:** `Ran 190 tests ... OK (skipped=3)`; 187 passing and 3 PostgreSQL-dependent skips. The new code adds 13 tests over the 177-test Phase 1 baseline (including one additional assertion in an existing PostgreSQL integration test). Your count may vary with local changes.

Stage only the patch files, not the downloaded patch or unrelated archives:

```powershell
git add docs/ADR-017-immutable-route-decision-evidence.md
git add migrations/0012_immutable_route_decision_records.sql
git add railone_execution/__init__.py railone_execution/decisions.py railone_execution/scoring.py railone_execution/service.py railone_execution/store.py
git add railone_postgres/execution.py scripts/check_repository_convergence.py
git add tests/test_postgres_live.py tests/test_route_decision_records.py
git diff --cached --check
git commit -m "feat(execution): persist immutable route decision evidence"
git push -u origin feat/v0.16-route-decision-evidence
```

If `git apply --check` fails due to an already-present file or changed context, **do not force-apply**. Run:

```powershell
git status --short
git apply --reverse --check .\RailOne_v0.16.0_phase2_route_decision_0012.patch
```

A successful reverse-check indicates that the patch contents are already present. Otherwise reconcile the branch against the file diff before editing.

## Main changes

- `railone_execution/decisions.py`: immutable, content-addressed `RouteDecisionRecord`; preserves original candidates, microsecond-precise telemetry, ranked results, policy weights, policy ID, exclusions and original selected route; independently recomputes scoring and exclusions.
- `railone_execution/scoring.py`: factors existing eligibility conditions into a single reason-reporting function, used by the original ranker; designed to preserve route eligibility and scores.
- `railone_execution/service.py`, `store.py`, `railone_postgres/execution.py`: create plan and decision atomically; idempotent if the exact original decision is replayed, conflict if same UTT tries to rewrite a different decision.
- `migrations/0012_immutable_route_decision_records.sql`: append-only, FK-linked persistence; original migrations unchanged.
- `tests/test_route_decision_records.py`, `tests/test_postgres_live.py`: replay, tamper, immutable snapshot, ambiguity and SQL read-back tests.
- `docs/ADR-017-immutable-route-decision-evidence.md`: normative intent and safety boundaries.

## Scope limitations

1. **No new RTT replay or granular fencing behavior** is enabled.
2. **No new license or adapter dispatch permission** is granted.
3. The record is content-addressed by SHA-256. **It is not independently signed.** A privileged database attacker who can rewrite both payload and hashes is not excluded by content hashing alone. Do not present the record as cryptographic nonrepudiation.
4. Migration 0012 is additive. Older ExecutionPlans remain without a decision row and are not backfilled by this change.
5. This records only the **initial plan decision**; future route re-scoring and mutations need separate append-only linked decision events.
6. The three skipped tests include the disposable PostgreSQL integration checks. Run CI with actual PostgreSQL before promoting this change to a pilot release gate.

## Suggested PR targeting

This feature branch is **stacked on** `feat/v0.16-currency-settlement-policy`. If Phase 1 is not merged into `main`, open the Phase 2 PR against the Phase 1 branch; otherwise update the feature branch onto the newly merged `main` and open the PR normally.
