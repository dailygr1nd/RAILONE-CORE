BEGIN;

-- ADR-017: original route-decision evidence for newly created execution plans.
-- No rewrite of historical plans or UTT/RTT artifacts is required.
CREATE TABLE railone.route_decision_records (
    decision_id text PRIMARY KEY CHECK (decision_id ~ '^RDEC-[A-F0-9]{32}$'),
    plan_id text NOT NULL UNIQUE REFERENCES railone.execution_plans(plan_id),
    utt_id text NOT NULL REFERENCES railone.accepted_utts(utt_id),
    decision_sha256 char(64) NOT NULL UNIQUE CHECK (decision_sha256 ~ '^[0-9a-f]{64}$'),
    schema_version integer NOT NULL CHECK (schema_version = 1),
    decision_payload jsonb NOT NULL,
    created_at timestamptz NOT NULL,
    CHECK (decision_payload ->> 'plan_id' = plan_id),
    CHECK (decision_payload ->> 'utt_id' = utt_id),
    CHECK ((decision_payload ->> 'schema_version')::integer = schema_version),
    CHECK (decision_payload ->> 'scoring_algorithm' = 'R1-INTEGER-WEIGHTED-BPS-V1')
);

CREATE INDEX route_decision_utt_lookup_idx
    ON railone.route_decision_records (utt_id, created_at DESC);

CREATE TRIGGER route_decision_records_append_only
BEFORE UPDATE OR DELETE ON railone.route_decision_records
FOR EACH ROW EXECUTE FUNCTION railone.reject_append_only_mutation();

COMMIT;
