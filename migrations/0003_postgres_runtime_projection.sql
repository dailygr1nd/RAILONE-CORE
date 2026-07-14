BEGIN;

CREATE TABLE IF NOT EXISTS railone.schema_migrations (
    version text PRIMARY KEY,
    migration_sha256 char(64) NOT NULL CHECK (migration_sha256 ~ '^[0-9a-f]{64}$'),
    applied_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE railone.execution_plans
    ADD COLUMN IF NOT EXISTS plan_state jsonb;

UPDATE railone.execution_plans
SET plan_state = jsonb_build_object(
    'remaining_route_ids', COALESCE(plan_snapshot -> 'remaining_route_ids', '[]'::jsonb),
    'failures', COALESCE(plan_snapshot -> 'failures', '[]'::jsonb),
    'previous_route_id', plan_snapshot -> 'previous_route_id'
)
WHERE plan_state IS NULL;

ALTER TABLE railone.execution_plans
    ALTER COLUMN plan_state SET NOT NULL;

CREATE TABLE railone.projection_inbox (
    consumer_name text NOT NULL,
    event_id text NOT NULL,
    event_payload_sha256 char(64) NOT NULL
        CHECK (event_payload_sha256 ~ '^[0-9a-f]{64}$'),
    consumed_at timestamptz NOT NULL,
    PRIMARY KEY (consumer_name, event_id)
);

CREATE TABLE railone.provider_outcome_projections (
    submission_id text PRIMARY KEY
        REFERENCES railone.provider_submissions (submission_id),
    utt_id text NOT NULL REFERENCES railone.accepted_utts (utt_id),
    rtt_id text NOT NULL REFERENCES railone.rtt_attempts (rtt_id),
    provider_id text NOT NULL,
    state text NOT NULL CHECK (
        state IN (
            'PREPARED', 'DISPATCHING', 'ACCEPTED_FOR_PROCESSING',
            'REJECTED', 'OUTCOME_UNKNOWN'
        )
    ),
    normalized_code text,
    external_reference text,
    rejection_disposition text CHECK (
        rejection_disposition IS NULL
        OR rejection_disposition IN ('RETRYABLE', 'TERMINAL')
    ),
    submission_version bigint NOT NULL CHECK (submission_version >= 1),
    source_event_id text NOT NULL,
    occurred_at timestamptz NOT NULL,
    projected_at timestamptz NOT NULL,
    UNIQUE (provider_id, external_reference)
);

CREATE INDEX provider_outcome_utt_idx
    ON railone.provider_outcome_projections (utt_id, occurred_at DESC);

CREATE TRIGGER projection_inbox_append_only
BEFORE UPDATE OR DELETE ON railone.projection_inbox
FOR EACH ROW EXECUTE FUNCTION railone.reject_append_only_mutation();

CREATE FUNCTION railone.guard_provider_outcome_projection_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.submission_id <> OLD.submission_id
       OR NEW.utt_id <> OLD.utt_id
       OR NEW.rtt_id <> OLD.rtt_id
       OR NEW.provider_id <> OLD.provider_id THEN
        RAISE EXCEPTION 'provider outcome lineage cannot change';
    END IF;
    IF NEW.submission_version <= OLD.submission_version THEN
        RAISE EXCEPTION 'provider outcome version must increase';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER provider_outcome_projection_guarded_update
BEFORE UPDATE ON railone.provider_outcome_projections
FOR EACH ROW EXECUTE FUNCTION railone.guard_provider_outcome_projection_update();

CREATE TRIGGER provider_outcome_projection_no_delete
BEFORE DELETE ON railone.provider_outcome_projections
FOR EACH ROW EXECUTE FUNCTION railone.reject_append_only_mutation();

COMMIT;
