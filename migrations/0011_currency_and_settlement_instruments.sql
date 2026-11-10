BEGIN;

-- Passive, append-only reference metadata. The presence of a currency or
-- profile in these tables NEVER authorizes payment dispatch or CBDC access.
CREATE TABLE railone.currency_definitions (
    currency_code text NOT NULL CHECK (currency_code ~ '^[A-Z]{3}$'),
    definition_version integer NOT NULL CHECK (definition_version >= 1),
    minor_unit_exponent smallint NOT NULL CHECK (minor_unit_exponent BETWEEN 0 AND 9),
    issuing_authority_ref text NOT NULL CHECK (length(issuing_authority_ref) BETWEEN 2 AND 128),
    standard_reference text NOT NULL CHECK (length(standard_reference) BETWEEN 2 AND 128),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (currency_code, definition_version)
);

CREATE TABLE railone.settlement_instrument_profiles (
    profile_id text NOT NULL,
    profile_version integer NOT NULL CHECK (profile_version >= 1),
    currency_code text NOT NULL,
    currency_definition_version integer NOT NULL,
    instrument_kind text NOT NULL CHECK (
        instrument_kind IN (
            'COMMERCIAL_BANK_MONEY', 'REGULATED_E_MONEY', 'RETAIL_CBDC', 'WHOLESALE_CBDC'
        )
    ),
    issuer_kind text NOT NULL CHECK (
        issuer_kind IN ('CENTRAL_BANK', 'LICENSED_BANK', 'REGULATED_EMONEY_ISSUER')
    ),
    issuer_institution_id text NOT NULL,
    operator_institution_id text NOT NULL,
    settlement_rail_id text NOT NULL,
    jurisdiction_country text NOT NULL CHECK (jurisdiction_country ~ '^[A-Z]{2}$'),
    environment text NOT NULL CHECK (environment IN ('SANDBOX', 'PILOT', 'PRODUCTION')),
    review_status text NOT NULL CHECK (review_status IN ('DECLARED', 'REVIEWED', 'SUSPENDED')),
    review_evidence_ref text,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (profile_id, profile_version),
    FOREIGN KEY (currency_code, currency_definition_version)
        REFERENCES railone.currency_definitions (currency_code, definition_version),
    CHECK ((review_status <> 'REVIEWED') OR review_evidence_ref IS NOT NULL),
    CHECK (
        (instrument_kind = 'COMMERCIAL_BANK_MONEY' AND issuer_kind = 'LICENSED_BANK') OR
        (instrument_kind = 'REGULATED_E_MONEY' AND issuer_kind = 'REGULATED_EMONEY_ISSUER') OR
        (instrument_kind IN ('RETAIL_CBDC', 'WHOLESALE_CBDC') AND issuer_kind = 'CENTRAL_BANK')
    )
);

-- Immutable revisions: policy changes create new versioned rows, never rewrites.
CREATE OR REPLACE FUNCTION railone.reject_currency_reference_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'currency and settlement-instrument records are append-only';
END;
$$;

CREATE TRIGGER currency_definitions_append_only
BEFORE UPDATE OR DELETE ON railone.currency_definitions
FOR EACH ROW EXECUTE FUNCTION railone.reject_currency_reference_mutation();

CREATE TRIGGER settlement_instrument_profiles_append_only
BEFORE UPDATE OR DELETE ON railone.settlement_instrument_profiles
FOR EACH ROW EXECUTE FUNCTION railone.reject_currency_reference_mutation();

CREATE INDEX settlement_instrument_profiles_lookup_idx
    ON railone.settlement_instrument_profiles
    (currency_code, instrument_kind, environment, review_status);

COMMIT;
