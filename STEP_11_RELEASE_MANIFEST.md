# Step 11A release manifest

- Build date: July 14, 2026
- Package version: 0.11.0
- Custody model: non-custodial
- Repository model: single converged pilot runtime
- Signature baseline: Ed25519
- Encryption target: AES-256-GCM envelope encryption
- Pilot security profile: R1-PILOT-SEC-1
- Baseline test discovery: 108
- Baseline runnable tests passed: 101
- Environment gates pending locally: 7

## Added controls

- one authoritative root package instead of cumulative runtime copies;
- explicit exclusion of the legacy prototype and committed keys;
- repository convergence validation;
- built-in private-material scanning;
- secret-safe environment template;
- pilot security policy and cryptographic role separation;
- GitHub Actions gate with optional HTTP dependencies and disposable PostgreSQL;
- dependency and workflow update monitoring; and
- authoritative Step 11 cleanup documentation.

## Remaining before simulated pilot traffic

- execute the CI job and obtain 108 passes with zero skips;
- revoke and rotate every private key exposed in the legacy repository;
- complete the reviewed Git history rewrite;
- implement isolated signing and continuity-secret providers;
- implement application envelope encryption for resolver/contact records;
- add the deployable sandbox composition root and workers; and
- complete M-PESA/provider and SMS gateway sandbox certification.
