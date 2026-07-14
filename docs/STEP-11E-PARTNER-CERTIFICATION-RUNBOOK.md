# Step 11E partner certification runbook

## Entry requirements

- Active Ed25519-signed institution capability manifest.
- Exact deployed adapter version matches the manifest binding.
- Synthetic partner accounts and contact destinations only.
- Authenticated HTTPS/mTLS or approved sandbox transport.
- Authenticated callback or active status/reconciliation evidence path.
- Isolated signing and encryption key services available.
- Migration `0010` applied.

An adapter without a declared finality evidence path is not certifiable.

## Execution

1. Create one immutable certification `run_id`.
2. Derive required scenarios from the signed manifest. Cross-border and callback
   cases are included only when those capabilities are declared.
3. Reset only the partner's disposable sandbox test fixtures. Never reset a
   shared or production schema.
4. Run each scenario with a bounded timeout and a fresh correlation identity.
5. Collect canonical events from RailOne's own audit boundaries. Do not accept
   a partner-authored success summary as trace evidence.
6. Verify content identifiers, adapter binding, UTT/RTT lineage, event order,
   external evidence hashes, history scopes and SMS counts.
7. Persist the run and traces append-only.
8. Sign and persist the pass or fail report through the isolated Ed25519 signer.
9. Review failed assertions and publish a new adapter version when behavior or
   capability material changes. Never overwrite a signed manifest or report.

## CI draft command

```powershell
railone-certify `
  --run-id RUN-PARTNER-001 `
  --adapter-binding partner.bank.ke@1.0.0 `
  --manifest-sha256 <64-lowercase-hex> `
  --trace-directory .\certification-traces `
  --output .\certification-draft.json
```

The command output is explicitly `UNSIGNED_CERTIFICATION_DRAFT`. It is useful
for partner CI feedback but is not authoritative evidence.

## Mandatory review

- Unknown outcomes produced no blind redispatch.
- Provider acceptance never became settlement without evidence.
- Duplicate callback produced one finality transition and two SMS records.
- Amount mismatch and invalid callback authentication left the RTT unfinished.
- P2P sender and receiver could read the UTT; unrelated identity was denied.
- Avia traffic used merchant/branch scopes rather than fabricated ContUIDs.
- Trace metadata contains no raw account, MSISDN, token, credential or SMS body.
- The report references the exact signed manifest payload hash.

## Promotion boundary

Passing Step 11E authorizes continued integration-pilot work only. Live funds
require partner and scheme certification, production trust anchors, security and
privacy reviews, load/failover/restore drills, reconciliation sign-off,
operational SLAs and regulatory approval.
