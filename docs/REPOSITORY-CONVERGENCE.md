# Repository Convergence Decision

## Decision

The cumulative Step 10 codebase is the sole parent of the RailOne pilot runtime.
Its contents are promoted to the repository root for version `0.11.0`.

The following are not part of the converged runtime:

- cumulative `step_01_*` through `step_10_*` wrapper directories;
- the pre-convergence root prototype;
- committed key material;
- generated Python, packaging, coverage, database, or log artifacts; and
- duplicated runbooks and release manifests.

Prior steps remain recoverable from Git tags and commit history. Database
migrations `0001` through `0006` are retained byte-for-byte and in order.

## Why

Multiple importable architectures create ambiguity about identity, ETK, UTT,
RTT, signing, settlement, and retry semantics. A pilot must have one build,
one migration chain, one test runner, and one authoritative documentation tree.

## Security exception

Private keys found in the pre-convergence snapshot are not retained as history
artifacts. They require revocation, rotation, and a separately reviewed Git
history rewrite.

## Supersession

`docs/STEP-10-BASELINE.md` preserves the cumulative technical history. The root
`README.md`, this decision, and `R1-PILOT-SEC-1` govern the converged pilot.
