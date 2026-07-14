# RailOne Security Policy

## Current support level

RailOne Core `0.15.x` is a partner-certification pilot baseline. It must not process real
customer funds or production personal data until the production security and
operational gates are approved.

## Reporting a vulnerability

Do not open a public issue containing exploit details, credentials, personal
data, or private key material. Report the issue through the repository's private
security-advisory channel and include:

- affected version or commit;
- impacted RailOne artifact or execution stage;
- reproduction steps using synthetic data;
- possible custody, duplication, privacy, or finality impact; and
- any evidence that credentials or signing keys were exposed.

Repository owners must configure the private reporting contact before inviting
external pilot participants.

## Key and secret rules

- Ed25519 private keys must be non-exportable in the deployment key service.
- Continuity HMAC keys must be purpose-separated from signing keys.
- Sandbox and production must never share keys or provider credentials.
- Secrets must not appear in source, fixtures, logs, traces, screenshots, or
  generated repository snapshots.
- Key identifiers and public keys may be stored; private key bytes may not.
- A suspected key exposure triggers revocation, rotation, evidence review, and
  Git-history remediation.

## Pilot severity priorities

- **Critical:** duplicate execution, forged settlement, signing-key exposure,
  authorization bypass, or access to raw account/contact endpoints.
- **High:** replay bypass, cross-tenant transaction disclosure, callback
  spoofing, or loss of reconciliation evidence.
- **Medium:** availability or observability defects that do not compromise
  execution correctness.

The pilot fails closed for critical and high-severity findings.
