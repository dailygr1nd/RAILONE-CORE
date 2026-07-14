BEGIN;

CREATE TABLE railone.api_token_revocations (
    token_id text PRIMARY KEY,
    expires_at timestamptz NOT NULL,
    reason text NOT NULL,
    revoked_at timestamptz NOT NULL
);

CREATE TABLE railone.api_rate_limit_windows (
    scope_key text PRIMARY KEY,
    window_started_at timestamptz NOT NULL,
    window_seconds integer NOT NULL CHECK (window_seconds BETWEEN 1 AND 3600),
    request_count bigint NOT NULL CHECK (request_count >= 1),
    updated_at timestamptz NOT NULL
);

CREATE TABLE railone.api_request_audit (
    audit_id text PRIMARY KEY,
    request_id text NOT NULL,
    principal_id text NOT NULL,
    token_id text,
    method text NOT NULL,
    route_template text NOT NULL,
    outcome text NOT NULL CHECK (
        outcome IN ('ALLOWED', 'DENIED', 'RATE_LIMITED', 'ERROR')
    ),
    status_code integer NOT NULL CHECK (status_code BETWEEN 100 AND 599),
    reason_code text NOT NULL,
    occurred_at timestamptz NOT NULL,
    audit_payload_sha256 char(64) NOT NULL UNIQUE
        CHECK (audit_payload_sha256 ~ '^[0-9a-f]{64}$'),
    signed_audit jsonb NOT NULL
);

CREATE INDEX api_request_audit_principal_idx
    ON railone.api_request_audit (principal_id, occurred_at DESC);

CREATE INDEX api_request_audit_request_idx
    ON railone.api_request_audit (request_id);

CREATE TRIGGER api_token_revocations_append_only
BEFORE UPDATE OR DELETE ON railone.api_token_revocations
FOR EACH ROW EXECUTE FUNCTION railone.reject_append_only_mutation();

CREATE TRIGGER api_request_audit_append_only
BEFORE UPDATE OR DELETE ON railone.api_request_audit
FOR EACH ROW EXECUTE FUNCTION railone.reject_append_only_mutation();

CREATE FUNCTION railone.guard_api_rate_limit_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.scope_key <> OLD.scope_key THEN
        RAISE EXCEPTION 'rate-limit scope cannot change';
    END IF;
    IF NEW.window_started_at = OLD.window_started_at
       AND NEW.request_count <> OLD.request_count + 1 THEN
        RAISE EXCEPTION 'active rate-limit count must advance exactly once';
    END IF;
    IF NEW.window_started_at > OLD.window_started_at
       AND NEW.request_count <> 1 THEN
        RAISE EXCEPTION 'new rate-limit window must start at one';
    END IF;
    IF NEW.window_started_at < OLD.window_started_at THEN
        RAISE EXCEPTION 'rate-limit window cannot move backwards';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER api_rate_limit_guarded_update
BEFORE UPDATE ON railone.api_rate_limit_windows
FOR EACH ROW EXECUTE FUNCTION railone.guard_api_rate_limit_update();

COMMIT;
