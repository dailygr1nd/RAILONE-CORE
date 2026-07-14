# ADR-011: Envelope Encryption and Synthetic Provider Effects

- Status: Accepted
- Date: 2026-07-14
- Scope: RailOne Step 11B simulated pilot

## Context

RailOne must exercise production-shaped confidentiality and outcome semantics
without moving live funds or storing real customer endpoints. Ed25519 already
protects artifact authenticity and integrity, but signatures do not encrypt
account references, MSISDNs, provider credentials, or notification content.

## Decision

Sensitive values use a versioned `A256GCM` envelope:

1. generate a fresh 256-bit data-encryption key (DEK) for every record;
2. encrypt the value with AES-256-GCM and a fresh 96-bit nonce;
3. bind purpose, record, owner, and field using canonical associated data;
4. wrap the DEK with a purpose-specific key-encryption key (KEK);
5. persist only the envelope, SHA-256 fingerprint, and non-secret metadata; and
6. unwrap only through an isolated key-service interface in deployed pilots.

The in-memory KEK adapter is test-only and marks readiness as
`SIMULATION_MEMORY`. Raw KEK bytes are never configuration values and never
enter source control.

The Step 11B effect broker is deterministic and synthetic-only. It supports:

- domestic bank (`BANK-KE`) accepted, rejected, unknown, and settlement effects;
- M-PESA (`MPESA-KE`) Daraja-shaped result/timeout effects;
- stable provider references and replay-safe idempotency;
- timeout-then-success drills; and
- refusal of endpoints that are not prefixed `SIM-`.

Simulation changes the external economic effect only. Quote acceptance, UTT
creation, ETK authority, RTT lineage, unknown-outcome blocking, callback
correlation, settlement evidence, and finality-gated notifications remain the
same production-intended semantics.

## Consequences

- Ed25519 remains the canonical RailOne signature scheme, not an encryption
  scheme.
- Existing account/contact bindings remain opaque in UTTs; plaintext resolution
  occurs only at the dispatch or delivery boundary.
- KEK rotation does not require re-encrypting payloads immediately because each
  envelope carries its key identifier. Rewrap automation is a later operational
  control.
- The local runtime cannot be promoted to a deployed pilot unchanged. A remote
  KMS/HSM client and durable PostgreSQL encrypted-secret store are mandatory.
- The simulator is not evidence of partner certification and cannot process
  production endpoints or credentials.
