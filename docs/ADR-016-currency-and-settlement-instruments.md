# ADR-016: Currency and Settlement-Instrument Reference Registry (v0.16 Alpha)

- **Status:** Proposed / implementation reference (not approved for live funds)
- **Parent:** RailOne ADR-015 and RO-DOC-TERM-001 / RO-DOC-ARCH-002
- **Scope:** New *passive* currency and instrument reference metadata; no changes to UTT/RTT, routing, dispatch, settlement or licensing

## Decision

Separate the denomination of a monetary obligation from the institutional form
of money that may settle it. A `CurrencyDefinition` identifies a sovereign
currency, a versioned minor-unit exponent and governance reference. A
`SettlementInstrumentProfile` declares one versioned settlement instrument and
its jurisdiction, issuer, operator, settlement rail and environment.

Permitted descriptive instrument classes are `COMMERCIAL_BANK_MONEY`,
`REGULATED_E_MONEY`, `RETAIL_CBDC`, and `WHOLESALE_CBDC`. This registry does not
include cryptoassets or stablecoins. In particular, a CBDC record represents
an *intended profile*, not access to a central-bank ledger or a CBDC settlement
right. Token-based CBDCs are still CBDCs for classification; the legal issuer,
permission model and actual ledger settlement evidence remain decisive.

## Non-negotiable boundaries

1. **No execution admission.** Registry presence, `REVIEWED` metadata or
   `PRODUCTION` label alone grants no route eligibility, partner entitlement,
   payment authorization, custody, external movement or finality.
2. **No automatic public registry ingestion.** Three-letter codes are only
   syntactically validated; this is not an independent ISO 4217 or sovereign
   issuer verification. Only trusted administrators may curate definitions.
3. **No effect on commercial truth.** UTT and RTT remain authoritative under
   existing contract and execution rules. Any currency precision transition
   must be handled under controlled versioning, not retroactive reinterpretation.
4. **No customer endpoints.** Raw accounts, phone numbers, access tokens and
   signing secrets do not belong in instrument profiles.
5. **New revisions, never rewrites.** Existing currency and instrument-version
   records are immutable; operator-approved changes append a version.
6. **No cryptocurrency support.** The v0.16 reference instrument-type enum
   deliberately excludes private cryptocurrencies, stablecoins and other
   cryptoassets. Validation of sovereign currency authenticity requires a
   separately governed allowlist or vetted reference authority.

## New files

- `railone_currency/models.py`: strict frozen models and serializable payloads
- `railone_currency/registry.py`: deterministic append-only metadata registry
- `railone_currency/__init__.py`: public metadata interface
- `migrations/0011_currency_and_settlement_instruments.sql`: append-only SQL records, foreign key and lookup index
- `tests/test_currency_instruments.py`: model, immutability, version and non-authority contract tests

## Source files changed

- `scripts/check_repository_convergence.py`: admit the new package and migration
- No change to UTT/RTT persistence, quote pricing or operational dispatch
- No changes to migration files `0001` through `0010`

## Future authority controls (NOT part of this change)

Authoritative reference verification; jurisdiction and corridor legal gates;
partner identity and adapter certification; settlement-rail contracts;
production issuer permissions; currency-exponent consistency against accepted
UTT; deterministic route selection; instrument-specific finality evidence.
The next planned migration is `0012` (route decision and economic-effect fencing).

## Acceptance gates

1. All existing unit tests continue passing plus new metadata tests.
2. All existing migration checksums remain unchanged; the new migration runs
   successfully on a disposable PostgreSQL database and is idempotent.
3. Convergence and secret scans pass on the clean source checkout.
4. Neither the schema nor reference registry is allowed to authorize dispatch.
5. No real bank, payment-rail or CBDC capability is inferred from synthetic IDs.
