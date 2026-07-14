BEGIN;

CREATE TABLE railone.partner_certification_runs (
    run_id text PRIMARY KEY,
    adapter_id text NOT NULL,
    adapter_version text NOT NULL,
    manifest_payload_sha256 text NOT NULL CHECK (manifest_payload_sha256 ~ '^[a-f0-9]{64}$'),
    suite_id text NOT NULL,
    suite_version text NOT NULL,
    status text NOT NULL CHECK (status IN ('RUNNING','PASSED','FAILED')),
    version bigint NOT NULL DEFAULT 1 CHECK (version >= 1),
    started_at timestamptz NOT NULL,
    completed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (adapter_id, adapter_version)
        REFERENCES railone.institution_adapter_manifests (adapter_id, adapter_version),
    CHECK ((status = 'RUNNING' AND completed_at IS NULL)
        OR (status IN ('PASSED','FAILED') AND completed_at IS NOT NULL))
);

CREATE OR REPLACE FUNCTION railone.guard_partner_certification_run_update()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.run_id <> OLD.run_id
       OR NEW.adapter_id <> OLD.adapter_id
       OR NEW.adapter_version <> OLD.adapter_version
       OR NEW.manifest_payload_sha256 <> OLD.manifest_payload_sha256
       OR NEW.suite_id <> OLD.suite_id
       OR NEW.suite_version <> OLD.suite_version
       OR NEW.started_at <> OLD.started_at
       OR NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION 'partner certification run birth material cannot change';
    END IF;
    IF OLD.status <> 'RUNNING' THEN
        RAISE EXCEPTION 'completed partner certification run is immutable';
    END IF;
    IF NEW.status NOT IN ('PASSED','FAILED') OR NEW.completed_at IS NULL THEN
        RAISE EXCEPTION 'partner certification run must complete explicitly';
    END IF;
    IF NEW.version <> OLD.version + 1 THEN
        RAISE EXCEPTION 'partner certification run version must advance exactly once';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER partner_certification_run_guard
BEFORE UPDATE ON railone.partner_certification_runs
FOR EACH ROW EXECUTE FUNCTION railone.guard_partner_certification_run_update();

CREATE OR REPLACE FUNCTION railone.reject_certification_evidence_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'partner certification evidence is append-only';
END;
$$;

CREATE TABLE railone.partner_certification_traces (
    trace_id text PRIMARY KEY,
    run_id text NOT NULL REFERENCES railone.partner_certification_runs (run_id),
    scenario text NOT NULL,
    adapter_binding_ref text NOT NULL,
    trace_payload jsonb NOT NULL,
    trace_payload_sha256 text NOT NULL CHECK (trace_payload_sha256 ~ '^[a-f0-9]{64}$'),
    started_at timestamptz NOT NULL,
    completed_at timestamptz NOT NULL CHECK (completed_at >= started_at),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (run_id, scenario),
    CHECK (trace_payload->>'trace_id' = trace_id),
    CHECK (trace_payload->>'run_id' = run_id),
    CHECK (trace_payload->>'adapter_binding_ref' = adapter_binding_ref)
);

CREATE TRIGGER partner_certification_trace_immutable
BEFORE UPDATE OR DELETE ON railone.partner_certification_traces
FOR EACH ROW EXECUTE FUNCTION railone.reject_certification_evidence_mutation();

CREATE TABLE railone.partner_certification_reports (
    report_id text PRIMARY KEY,
    run_id text NOT NULL UNIQUE REFERENCES railone.partner_certification_runs (run_id),
    adapter_id text NOT NULL,
    adapter_version text NOT NULL,
    suite_id text NOT NULL,
    suite_version text NOT NULL,
    status text NOT NULL CHECK (status IN ('PASSED','FAILED')),
    evidence_classification text NOT NULL CHECK (
        evidence_classification = 'PARTNER_SANDBOX'
    ),
    signed_report jsonb NOT NULL,
    payload_sha256 text NOT NULL CHECK (payload_sha256 ~ '^[a-f0-9]{64}$'),
    signing_key_id text NOT NULL,
    issued_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (adapter_id, adapter_version)
        REFERENCES railone.institution_adapter_manifests (adapter_id, adapter_version),
    CHECK (signed_report->'payload'->>'report_id' = report_id),
    CHECK (signed_report->'protected'->>'typ' = 'railone.partner_certification_report'),
    CHECK (signed_report->'protected'->>'alg' = 'EdDSA'),
    CHECK (signed_report->'protected'->>'crv' = 'Ed25519'),
    CHECK (signed_report->'protected'->>'kid' = signing_key_id),
    CHECK (signed_report->'protected'->>'payload_sha256' = payload_sha256)
);

CREATE TRIGGER partner_certification_report_immutable
BEFORE UPDATE OR DELETE ON railone.partner_certification_reports
FOR EACH ROW EXECUTE FUNCTION railone.reject_certification_evidence_mutation();

CREATE INDEX partner_certification_run_adapter_idx
    ON railone.partner_certification_runs
    (adapter_id, adapter_version, suite_version, started_at DESC);

COMMIT;
