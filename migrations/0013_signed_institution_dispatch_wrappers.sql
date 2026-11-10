BEGIN;

-- Phase 3: signed canonical instruction envelopes. These rows are NOT dispatch
-- permits and do not prove settlement, fence release, or provider conformance.
-- Only a trusted RailOne service may issue or persist these envelopes.
CREATE TABLE railone.institution_dispatch_wrappers (
    envelope_id text PRIMARY KEY CHECK (envelope_id ~ '^IW-[A-F0-9]{32}$'),
    rtt_id text NOT NULL UNIQUE REFERENCES railone.rtt_attempts(rtt_id),
    plan_id text NOT NULL REFERENCES railone.execution_plans(plan_id),
    utt_id text NOT NULL REFERENCES railone.accepted_utts(utt_id),
    route_decision_sha256 char(64) NOT NULL
       REFERENCES railone.route_decision_records(decision_sha256),
    adapter_binding_ref text NOT NULL
       REFERENCES railone.institution_adapter_manifests(binding_ref),
    wrapper_sha256 char(64) NOT NULL UNIQUE CHECK (wrapper_sha256 ~ '^[a-f0-9]{64}$'),
    signed_artifact jsonb NOT NULL,
    signing_key_id text NOT NULL,
    issued_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL CHECK (expires_at > issued_at AND expires_at <= issued_at + interval '60 seconds'),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (signed_artifact->'protected'->>'typ' = 'railone.institution_dispatch_wrapper'),
    CHECK (signed_artifact->'protected'->>'alg' = 'EdDSA'),
    CHECK (signed_artifact->'protected'->>'crv' = 'Ed25519'),
    CHECK (signed_artifact->'protected'->>'kid' = signing_key_id),
    CHECK (signed_artifact->'protected'->>'iss' = 'RAILONE'),
    CHECK (signed_artifact->'payload'->>'envelope_id' = envelope_id),
    CHECK (signed_artifact->'payload'->'trace_identifiers'->>'rtt_id' = rtt_id),
    CHECK (signed_artifact->'payload'->'trace_identifiers'->>'plan_id' = plan_id),
    CHECK (signed_artifact->'payload'->'trace_identifiers'->>'utt_id' = utt_id),
    CHECK (signed_artifact->'payload'->'execution_binding'->>'adapter_binding_ref' = adapter_binding_ref),
    CHECK (signed_artifact->'payload'->'execution_binding'->>'route_decision_digest' = route_decision_sha256)
);

CREATE INDEX institution_dispatch_wrappers_plan_idx
    ON railone.institution_dispatch_wrappers(plan_id, created_at DESC);

CREATE TRIGGER institution_dispatch_wrappers_append_only
BEFORE UPDATE OR DELETE ON railone.institution_dispatch_wrappers
FOR EACH ROW EXECUTE FUNCTION railone.reject_append_only_mutation();

COMMIT;
