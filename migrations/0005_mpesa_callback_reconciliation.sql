BEGIN;

ALTER TABLE railone.provider_submissions
    ADD COLUMN provider_context jsonb NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN railone.provider_callback_inbox.raw_payload IS
    'Sanitized allowlisted callback fields only; never the unredacted provider body';

CREATE OR REPLACE FUNCTION railone.guard_rtt_update()
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
    IF OLD.state = 'CREATED'
       AND NEW.state NOT IN ('FAILED','SUCCEEDED','RECONCILIATION_REQUIRED') THEN
        RAISE EXCEPTION 'invalid initial RTT outcome transition';
    END IF;
    IF OLD.state = 'RECONCILIATION_REQUIRED'
       AND NEW.state NOT IN ('FAILED','SUCCEEDED') THEN
        RAISE EXCEPTION 'reconciled RTT must become failed or succeeded';
    END IF;
    IF OLD.state IN ('FAILED','SUCCEEDED') THEN
        RAISE EXCEPTION 'RTT operational outcome is terminal';
    END IF;
    RETURN NEW;
END;
$$;

COMMIT;
