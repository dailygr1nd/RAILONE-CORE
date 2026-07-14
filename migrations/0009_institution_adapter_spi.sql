BEGIN;

CREATE TABLE railone.institution_adapter_manifests (
    adapter_id text NOT NULL,
    adapter_version text NOT NULL,
    binding_ref text GENERATED ALWAYS AS (adapter_id || '@' || adapter_version) STORED,
    provider_id text NOT NULL,
    network_id text NOT NULL,
    environment text NOT NULL CHECK (environment IN ('SANDBOX','PILOT','PRODUCTION')),
    certification_status text NOT NULL CHECK (
        certification_status IN ('DRAFT','CONFORMANCE','CERTIFIED','SUSPENDED')
    ),
    manifest_id text NOT NULL,
    manifest_version integer NOT NULL CHECK (manifest_version >= 1),
    signed_manifest jsonb NOT NULL,
    payload_sha256 text NOT NULL CHECK (payload_sha256 ~ '^[a-f0-9]{64}$'),
    signing_key_id text NOT NULL,
    issued_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL CHECK (expires_at > issued_at),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (adapter_id, adapter_version),
    UNIQUE (binding_ref),
    UNIQUE (manifest_id, manifest_version),
    UNIQUE (adapter_id, adapter_version, manifest_id, manifest_version),
    CHECK (signed_manifest->'protected'->>'typ' = 'railone.institution_capability_manifest'),
    CHECK (signed_manifest->'protected'->>'alg' = 'EdDSA'),
    CHECK (signed_manifest->'protected'->>'crv' = 'Ed25519'),
    CHECK (signed_manifest->'protected'->>'kid' = signing_key_id),
    CHECK (signed_manifest->'protected'->>'payload_sha256' = payload_sha256)
);

CREATE OR REPLACE FUNCTION railone.reject_institution_manifest_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'institution adapter manifests are append-only; publish a new version';
END;
$$;

CREATE TRIGGER institution_adapter_manifest_immutable
BEFORE UPDATE OR DELETE ON railone.institution_adapter_manifests
FOR EACH ROW EXECUTE FUNCTION railone.reject_institution_manifest_mutation();

CREATE TABLE railone.institution_adapter_bindings (
    binding_id text PRIMARY KEY,
    rtt_id text NOT NULL UNIQUE REFERENCES railone.rtt_attempts (rtt_id),
    adapter_id text NOT NULL,
    adapter_version text NOT NULL,
    manifest_id text NOT NULL,
    manifest_version integer NOT NULL,
    manifest_payload_sha256 text NOT NULL CHECK (manifest_payload_sha256 ~ '^[a-f0-9]{64}$'),
    bound_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (adapter_id, adapter_version, manifest_id, manifest_version)
        REFERENCES railone.institution_adapter_manifests
        (adapter_id, adapter_version, manifest_id, manifest_version)
);

CREATE TRIGGER institution_adapter_binding_immutable
BEFORE UPDATE OR DELETE ON railone.institution_adapter_bindings
FOR EACH ROW EXECUTE FUNCTION railone.reject_institution_manifest_mutation();

CREATE TABLE railone.institution_adapter_events (
    event_id text PRIMARY KEY,
    rtt_id text NOT NULL REFERENCES railone.rtt_attempts (rtt_id),
    adapter_id text NOT NULL,
    adapter_version text NOT NULL,
    provider_id text NOT NULL,
    external_reference text NOT NULL,
    observation_type text NOT NULL CHECK (
        observation_type IN ('CALLBACK','STATUS_QUERY','RECONCILIATION')
    ),
    normalized_outcome text NOT NULL CHECK (
        normalized_outcome IN (
            'PENDING','CONFIRMED_SUCCESS','CONFIRMED_FAILURE',
            'OUTCOME_UNKNOWN','RECONCILIATION_REQUIRED'
        )
    ),
    finality_level text NOT NULL CHECK (
        finality_level IN ('NONE','PROCESSING','DEBIT_CONFIRMED','CREDIT_CONFIRMED','SETTLED')
    ),
    evidence_sha256 text NOT NULL CHECK (evidence_sha256 ~ '^[a-f0-9]{64}$'),
    signed_event jsonb NOT NULL,
    observed_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (adapter_id, adapter_version)
        REFERENCES railone.institution_adapter_manifests (adapter_id, adapter_version),
    UNIQUE (adapter_id, adapter_version, external_reference, evidence_sha256)
);

CREATE TRIGGER institution_adapter_event_immutable
BEFORE UPDATE OR DELETE ON railone.institution_adapter_events
FOR EACH ROW EXECUTE FUNCTION railone.reject_institution_manifest_mutation();

CREATE TABLE railone.adapter_conformance_records (
    conformance_id text PRIMARY KEY,
    adapter_id text NOT NULL,
    adapter_version text NOT NULL,
    suite_version text NOT NULL,
    result text NOT NULL CHECK (result IN ('PASSED','FAILED')),
    report_sha256 text NOT NULL CHECK (report_sha256 ~ '^[a-f0-9]{64}$'),
    signed_report jsonb NOT NULL,
    executed_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (adapter_id, adapter_version)
        REFERENCES railone.institution_adapter_manifests (adapter_id, adapter_version),
    UNIQUE (adapter_id, adapter_version, suite_version, report_sha256)
);

CREATE TRIGGER adapter_conformance_record_immutable
BEFORE UPDATE OR DELETE ON railone.adapter_conformance_records
FOR EACH ROW EXECUTE FUNCTION railone.reject_institution_manifest_mutation();

CREATE INDEX institution_adapter_manifest_eligibility_idx
    ON railone.institution_adapter_manifests
    (environment, certification_status, provider_id, expires_at);
CREATE INDEX institution_adapter_events_reconciliation_idx
    ON railone.institution_adapter_events
    (provider_id, external_reference, observed_at);

COMMIT;
