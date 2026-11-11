BEGIN;

-- Redacted, append-only admission decisions. Sensitive account data, private
-- keys and complete ETK payloads never belong in this table.
CREATE TABLE railone.institution_security_audit (
    event_id uuid PRIMARY KEY,
    occurred_at timestamptz NOT NULL,
    event_type text NOT NULL CHECK (event_type IN
        ('BILATERAL_AUTH_REJECTED', 'INSTITUTION_DISPATCH_REJECTED')),
    operation text NOT NULL CHECK (operation IN ('ACCEPT', 'PLAN', 'RTT_CREATE', 'PREFLIGHT', 'ADMIT')),
    correlation_ref text NOT NULL CHECK (length(correlation_ref) BETWEEN 1 AND 128),
    reason_code text NOT NULL CHECK (length(reason_code) BETWEEN 1 AND 72),
    outcome text NOT NULL DEFAULT 'DENIED' CHECK (outcome = 'DENIED')
);

CREATE INDEX institution_security_audit_recent_idx
    ON railone.institution_security_audit (occurred_at DESC, event_type);

CREATE TRIGGER institution_security_audit_append_only
BEFORE UPDATE OR DELETE ON railone.institution_security_audit
FOR EACH ROW EXECUTE FUNCTION railone.reject_append_only_mutation();

COMMIT;
