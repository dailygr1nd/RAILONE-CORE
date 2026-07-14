BEGIN;

CREATE TABLE railone.acceptance_idempotency (
    idempotency_key text PRIMARY KEY,
    request_sha256 char(64) NOT NULL CHECK (request_sha256 ~ '^[0-9a-f]{64}$'),
    utt_id text NOT NULL UNIQUE REFERENCES railone.accepted_utts (utt_id),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE railone.execution_authorities (
    authority_id text PRIMARY KEY,
    authority_type text NOT NULL CHECK (authority_type IN ('ETK_S', 'ETK_R')),
    utt_id text NOT NULL REFERENCES railone.accepted_utts (utt_id),
    payload_sha256 char(64) NOT NULL UNIQUE CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
    signed_envelope jsonb NOT NULL,
    created_at timestamptz NOT NULL,
    UNIQUE (utt_id, authority_type, authority_id)
);

CREATE TABLE railone.execution_plans (
    plan_id text PRIMARY KEY,
    utt_id text NOT NULL UNIQUE REFERENCES railone.accepted_utts (utt_id),
    plan_snapshot jsonb NOT NULL,
    status text NOT NULL CHECK (
        status IN ('ACTIVE', 'RECONCILIATION_REQUIRED', 'FAILED', 'EXHAUSTED', 'FINALIZED')
    ),
    attempts_used integer NOT NULL CHECK (attempts_used >= 0),
    max_attempts integer NOT NULL CHECK (max_attempts BETWEEN 1 AND 10),
    routing_budget_minor bigint NOT NULL CHECK (routing_budget_minor >= 0),
    routing_cost_spent_minor bigint NOT NULL CHECK (routing_cost_spent_minor >= 0),
    current_rtt_id text,
    previous_rtt_id text,
    successful_route_id text,
    version bigint NOT NULL CHECK (version >= 1),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    CHECK (attempts_used <= max_attempts)
);

CREATE TABLE railone.rtt_attempts (
    rtt_id text PRIMARY KEY CHECK (rtt_id ~ '^RTT-[A-F0-9]{32}$'),
    utt_id text NOT NULL REFERENCES railone.accepted_utts (utt_id),
    plan_id text NOT NULL REFERENCES railone.execution_plans (plan_id),
    attempt_number integer NOT NULL CHECK (attempt_number >= 1),
    route_id text NOT NULL,
    rtt_payload_sha256 char(64) NOT NULL UNIQUE CHECK (rtt_payload_sha256 ~ '^[0-9a-f]{64}$'),
    signed_rtt jsonb NOT NULL,
    state text NOT NULL CHECK (
        state IN ('CREATED', 'FAILED', 'SUCCEEDED', 'RECONCILIATION_REQUIRED')
    ),
    failure_code text,
    actual_cost_minor bigint CHECK (actual_cost_minor >= 0),
    version bigint NOT NULL DEFAULT 1 CHECK (version >= 1),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    UNIQUE (plan_id, attempt_number),
    UNIQUE (utt_id, rtt_id)
);

ALTER TABLE railone.execution_plans
    ADD CONSTRAINT execution_plans_current_rtt_fk
    FOREIGN KEY (current_rtt_id)
    REFERENCES railone.rtt_attempts (rtt_id)
    DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE railone.execution_plans
    ADD CONSTRAINT execution_plans_previous_rtt_fk
    FOREIGN KEY (previous_rtt_id)
    REFERENCES railone.rtt_attempts (rtt_id)
    DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE railone.provider_submissions (
    submission_id text PRIMARY KEY,
    provider_id text NOT NULL,
    idempotency_key text NOT NULL UNIQUE,
    request_sha256 char(64) NOT NULL UNIQUE CHECK (request_sha256 ~ '^[0-9a-f]{64}$'),
    utt_id text NOT NULL REFERENCES railone.accepted_utts (utt_id),
    rtt_id text NOT NULL UNIQUE REFERENCES railone.rtt_attempts (rtt_id),
    state text NOT NULL CHECK (
        state IN ('PREPARED', 'DISPATCHING', 'ACCEPTED', 'REJECTED', 'UNKNOWN')
    ),
    dispatch_attempts integer NOT NULL DEFAULT 0 CHECK (dispatch_attempts >= 0),
    normalized_code text,
    external_reference text,
    rejection_disposition text CHECK (
        rejection_disposition IS NULL
        OR rejection_disposition IN ('RETRYABLE', 'TERMINAL')
    ),
    version bigint NOT NULL DEFAULT 1 CHECK (version >= 1),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    UNIQUE (provider_id, external_reference)
);

CREATE TABLE railone.signed_outbox (
    event_id text PRIMARY KEY,
    aggregate_type text NOT NULL,
    aggregate_id text NOT NULL,
    event_type text NOT NULL,
    signed_event jsonb NOT NULL,
    event_payload_sha256 char(64) NOT NULL UNIQUE CHECK (event_payload_sha256 ~ '^[0-9a-f]{64}$'),
    delivery_state text NOT NULL CHECK (
        delivery_state IN ('PENDING', 'IN_FLIGHT', 'PUBLISHED', 'DEAD_LETTER')
    ),
    delivery_attempts integer NOT NULL DEFAULT 0 CHECK (delivery_attempts >= 0),
    available_at timestamptz NOT NULL,
    lease_owner text,
    lease_until timestamptz,
    last_error text,
    published_at timestamptz,
    version bigint NOT NULL DEFAULT 1 CHECK (version >= 1),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    CHECK (
        (delivery_state = 'IN_FLIGHT' AND lease_owner IS NOT NULL AND lease_until IS NOT NULL)
        OR (delivery_state <> 'IN_FLIGHT' AND lease_owner IS NULL AND lease_until IS NULL)
    ),
    CHECK (
        (delivery_state = 'PUBLISHED' AND published_at IS NOT NULL)
        OR delivery_state <> 'PUBLISHED'
    )
);

CREATE INDEX signed_outbox_claim_idx
    ON railone.signed_outbox (delivery_state, available_at, lease_until, event_id);

CREATE TABLE railone.provider_callback_inbox (
    provider_id text NOT NULL,
    provider_event_id text NOT NULL,
    payload_sha256 char(64) NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
    raw_payload jsonb NOT NULL,
    signature_valid boolean NOT NULL,
    received_at timestamptz NOT NULL,
    applied_at timestamptz,
    PRIMARY KEY (provider_id, provider_event_id)
);

CREATE TABLE railone.reconciliation_cases (
    case_id text PRIMARY KEY,
    utt_id text NOT NULL REFERENCES railone.accepted_utts (utt_id),
    rtt_id text NOT NULL REFERENCES railone.rtt_attempts (rtt_id),
    submission_id text NOT NULL REFERENCES railone.provider_submissions (submission_id),
    reason_code text NOT NULL,
    status text NOT NULL CHECK (status IN ('OPEN', 'EVIDENCE_RECEIVED', 'RESOLVED')),
    resolution text CHECK (
        resolution IS NULL OR resolution IN ('CONFIRMED_SUCCESS', 'CONFIRMED_FAILURE')
    ),
    evidence_reference text,
    version bigint NOT NULL DEFAULT 1 CHECK (version >= 1),
    opened_at timestamptz NOT NULL,
    resolved_at timestamptz,
    updated_at timestamptz NOT NULL,
    UNIQUE (rtt_id, submission_id)
);

CREATE TRIGGER acceptance_idempotency_append_only
BEFORE UPDATE OR DELETE ON railone.acceptance_idempotency
FOR EACH ROW EXECUTE FUNCTION railone.reject_append_only_mutation();

CREATE TRIGGER execution_authorities_append_only
BEFORE UPDATE OR DELETE ON railone.execution_authorities
FOR EACH ROW EXECUTE FUNCTION railone.reject_append_only_mutation();

CREATE FUNCTION railone.guard_rtt_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.rtt_id <> OLD.rtt_id
       OR NEW.utt_id <> OLD.utt_id
       OR NEW.plan_id <> OLD.plan_id
       OR NEW.attempt_number <> OLD.attempt_number
       OR NEW.route_id <> OLD.route_id
       OR NEW.rtt_payload_sha256 <> OLD.rtt_payload_sha256
       OR NEW.signed_rtt <> OLD.signed_rtt
       OR NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION 'immutable RTT birth fields cannot change';
    END IF;
    IF NEW.version <> OLD.version + 1 THEN
        RAISE EXCEPTION 'RTT version must advance exactly once';
    END IF;
    IF OLD.state <> 'CREATED' THEN
        RAISE EXCEPTION 'RTT operational outcome is terminal';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER rtt_attempts_guarded_update
BEFORE UPDATE ON railone.rtt_attempts
FOR EACH ROW EXECUTE FUNCTION railone.guard_rtt_update();

CREATE TRIGGER rtt_attempts_no_delete
BEFORE DELETE ON railone.rtt_attempts
FOR EACH ROW EXECUTE FUNCTION railone.reject_append_only_mutation();

CREATE FUNCTION railone.guard_signed_outbox_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.event_id <> OLD.event_id
       OR NEW.aggregate_type <> OLD.aggregate_type
       OR NEW.aggregate_id <> OLD.aggregate_id
       OR NEW.event_type <> OLD.event_type
       OR NEW.signed_event <> OLD.signed_event
       OR NEW.event_payload_sha256 <> OLD.event_payload_sha256
       OR NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION 'signed outbox event material cannot change';
    END IF;
    IF NEW.version <> OLD.version + 1 THEN
        RAISE EXCEPTION 'outbox version must advance exactly once';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER signed_outbox_guarded_update
BEFORE UPDATE ON railone.signed_outbox
FOR EACH ROW EXECUTE FUNCTION railone.guard_signed_outbox_update();

CREATE TRIGGER signed_outbox_no_delete
BEFORE DELETE ON railone.signed_outbox
FOR EACH ROW EXECUTE FUNCTION railone.reject_append_only_mutation();

CREATE FUNCTION railone.guard_execution_plan_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.plan_id <> OLD.plan_id
       OR NEW.utt_id <> OLD.utt_id
       OR NEW.plan_snapshot <> OLD.plan_snapshot
       OR NEW.max_attempts <> OLD.max_attempts
       OR NEW.routing_budget_minor <> OLD.routing_budget_minor
       OR NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION 'immutable ExecutionPlan fields cannot change';
    END IF;
    IF NEW.version <> OLD.version + 1 THEN
        RAISE EXCEPTION 'ExecutionPlan version must advance exactly once';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER execution_plans_guarded_update
BEFORE UPDATE ON railone.execution_plans
FOR EACH ROW EXECUTE FUNCTION railone.guard_execution_plan_update();

CREATE TRIGGER execution_plans_no_delete
BEFORE DELETE ON railone.execution_plans
FOR EACH ROW EXECUTE FUNCTION railone.reject_append_only_mutation();

CREATE FUNCTION railone.guard_provider_submission_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.submission_id <> OLD.submission_id
       OR NEW.provider_id <> OLD.provider_id
       OR NEW.idempotency_key <> OLD.idempotency_key
       OR NEW.request_sha256 <> OLD.request_sha256
       OR NEW.utt_id <> OLD.utt_id
       OR NEW.rtt_id <> OLD.rtt_id
       OR NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION 'immutable provider submission fields cannot change';
    END IF;
    IF NEW.version <> OLD.version + 1 THEN
        RAISE EXCEPTION 'provider submission version must advance exactly once';
    END IF;
    IF OLD.state IN ('ACCEPTED', 'REJECTED', 'UNKNOWN') THEN
        RAISE EXCEPTION 'provider submission is terminal';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER provider_submissions_guarded_update
BEFORE UPDATE ON railone.provider_submissions
FOR EACH ROW EXECUTE FUNCTION railone.guard_provider_submission_update();

CREATE TRIGGER provider_submissions_no_delete
BEFORE DELETE ON railone.provider_submissions
FOR EACH ROW EXECUTE FUNCTION railone.reject_append_only_mutation();

CREATE FUNCTION railone.guard_provider_callback_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.provider_id <> OLD.provider_id
       OR NEW.provider_event_id <> OLD.provider_event_id
       OR NEW.payload_sha256 <> OLD.payload_sha256
       OR NEW.raw_payload <> OLD.raw_payload
       OR NEW.signature_valid <> OLD.signature_valid
       OR NEW.received_at <> OLD.received_at THEN
        RAISE EXCEPTION 'provider callback evidence cannot change';
    END IF;
    IF OLD.applied_at IS NOT NULL OR NEW.applied_at IS NULL THEN
        RAISE EXCEPTION 'provider callback may be applied exactly once';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER provider_callback_inbox_guarded_update
BEFORE UPDATE ON railone.provider_callback_inbox
FOR EACH ROW EXECUTE FUNCTION railone.guard_provider_callback_update();

CREATE TRIGGER provider_callback_inbox_no_delete
BEFORE DELETE ON railone.provider_callback_inbox
FOR EACH ROW EXECUTE FUNCTION railone.reject_append_only_mutation();

COMMIT;
