-- Phase 6. Forward-only; do not amend previously checksum-locked migrations.
-- This schema models a UTT-wide economic hold and independently tracked RTT work.
-- A lease timeout MUST NOT clear a potential provider financial effect.
BEGIN;

CREATE TABLE railone.utt_economic_fences (
    utt_id text PRIMARY KEY REFERENCES railone.accepted_utts (utt_id),
    fence_epoch bigint NOT NULL CHECK (fence_epoch >= 1),
    state text NOT NULL CHECK (state IN ('OPEN','HELD','FINALIZED')),
    current_rtt_id text REFERENCES railone.rtt_attempts (rtt_id),
    last_release_evidence_id text,
    version bigint NOT NULL DEFAULT 1 CHECK (version >= 1),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    CHECK ((state = 'OPEN' AND current_rtt_id IS NULL)
        OR (state IN ('HELD','FINALIZED') AND current_rtt_id IS NOT NULL))
);

CREATE TABLE railone.rtt_operational_fences (
    rtt_id text PRIMARY KEY REFERENCES railone.rtt_attempts (rtt_id),
    utt_id text NOT NULL REFERENCES railone.accepted_utts (utt_id),
    fence_epoch bigint NOT NULL CHECK (fence_epoch >= 1),
    request_sha256 char(64) NOT NULL CHECK (request_sha256 ~ '^[0-9a-f]{64}$'),
    state text NOT NULL CHECK (state IN (
        'RESERVED','ACCEPTED_FOR_PROCESSING','REJECTED','UNKNOWN',
        'RELEASED_NO_EFFECT','SETTLED'
    )),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    UNIQUE (utt_id, fence_epoch),
    FOREIGN KEY (utt_id, rtt_id) REFERENCES railone.rtt_attempts (utt_id, rtt_id)
);

CREATE TABLE railone.economic_fence_no_effect_evidence (
    evidence_id text PRIMARY KEY,
    utt_id text NOT NULL REFERENCES railone.accepted_utts (utt_id),
    rtt_id text NOT NULL REFERENCES railone.rtt_operational_fences (rtt_id),
    signed_evidence jsonb NOT NULL,
    evidence_sha256 char(64) NOT NULL CHECK (evidence_sha256 ~ '^[0-9a-f]{64}$'),
    signing_key_id text NOT NULL,
    recorded_at timestamptz NOT NULL,
    UNIQUE (utt_id, rtt_id),
    CHECK (signed_evidence->'protected'->>'typ' = 'railone.no_effect_evidence'),
    CHECK (signed_evidence->'protected'->>'payload_sha256' = evidence_sha256),
    CHECK (signed_evidence->'payload'->>'evidence_id' = evidence_id)
);

-- A released epoch must reference stored signed no-effect proof.
ALTER TABLE railone.utt_economic_fences
ADD CONSTRAINT utt_fence_release_evidence_fk
FOREIGN KEY (last_release_evidence_id)
REFERENCES railone.economic_fence_no_effect_evidence (evidence_id);

CREATE FUNCTION railone.guard_utt_economic_fence_update() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.utt_id <> OLD.utt_id OR NEW.created_at <> OLD.created_at
       OR NEW.version <> OLD.version + 1 THEN
        RAISE EXCEPTION 'economic fence identity/version mismatch';
    END IF;
    IF OLD.state = 'OPEN' AND NEW.state = 'HELD'
       AND NEW.fence_epoch = OLD.fence_epoch
       AND NEW.current_rtt_id IS NOT NULL
       AND NEW.last_release_evidence_id IS NOT DISTINCT FROM OLD.last_release_evidence_id THEN
        RETURN NEW;
    END IF;
    IF OLD.state = 'HELD' AND NEW.state = 'OPEN'
       AND NEW.fence_epoch = OLD.fence_epoch + 1
       AND NEW.current_rtt_id IS NULL
       AND NEW.last_release_evidence_id IS NOT NULL
       AND EXISTS (
           SELECT 1 FROM railone.economic_fence_no_effect_evidence e
           WHERE e.evidence_id = NEW.last_release_evidence_id
             AND e.utt_id = OLD.utt_id AND e.rtt_id = OLD.current_rtt_id
       ) THEN
        RETURN NEW;
    END IF;
    IF OLD.state = 'HELD' AND NEW.state = 'FINALIZED'
       AND NEW.current_rtt_id = OLD.current_rtt_id
       AND NEW.fence_epoch = OLD.fence_epoch
       AND NEW.last_release_evidence_id IS NOT DISTINCT FROM OLD.last_release_evidence_id THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'unsafe UTT economic fence transition';
END;
$$;
CREATE TRIGGER utt_economic_fence_update_guard
BEFORE UPDATE ON railone.utt_economic_fences
FOR EACH ROW EXECUTE FUNCTION railone.guard_utt_economic_fence_update();

CREATE FUNCTION railone.guard_rtt_operational_fence_update() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.rtt_id <> OLD.rtt_id OR NEW.utt_id <> OLD.utt_id
       OR NEW.fence_epoch <> OLD.fence_epoch
       OR NEW.request_sha256 <> OLD.request_sha256
       OR NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION 'RTT operational fence identity cannot change';
    END IF;
    IF OLD.state = 'RESERVED'
       AND NEW.state IN ('ACCEPTED_FOR_PROCESSING','REJECTED','UNKNOWN') THEN
        RETURN NEW;
    END IF;
    IF OLD.state IN ('RESERVED','ACCEPTED_FOR_PROCESSING','REJECTED','UNKNOWN')
       AND NEW.state = 'RELEASED_NO_EFFECT'
       AND EXISTS (
           SELECT 1 FROM railone.economic_fence_no_effect_evidence e
           WHERE e.utt_id = OLD.utt_id AND e.rtt_id = OLD.rtt_id
       ) THEN
        RETURN NEW;
    END IF;
    IF OLD.state IN ('RESERVED','ACCEPTED_FOR_PROCESSING','REJECTED','UNKNOWN')
       AND NEW.state = 'SETTLED'
       AND EXISTS (
           SELECT 1 FROM railone.settlement_evidence e
           JOIN railone.provider_submissions s
             ON s.provider_id = e.provider_id
            AND s.external_reference = e.provider_transaction_id
           WHERE e.utt_id = OLD.utt_id AND s.rtt_id = OLD.rtt_id
       ) THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'unsafe RTT operational fence transition';
END;
$$;
CREATE TRIGGER rtt_operational_fence_update_guard
BEFORE UPDATE ON railone.rtt_operational_fences
FOR EACH ROW EXECUTE FUNCTION railone.guard_rtt_operational_fence_update();

-- Settlement writers and fence writers lock the same immutable UTT row. A
-- release cannot race a concurrent settlement-evidence insertion unnoticed.
CREATE FUNCTION railone.lock_utt_before_settlement_evidence() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    PERFORM 1 FROM railone.accepted_utts WHERE utt_id = NEW.utt_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'settlement evidence refers to unknown UTT';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER settlement_evidence_utt_lock
BEFORE INSERT ON railone.settlement_evidence
FOR EACH ROW EXECUTE FUNCTION railone.lock_utt_before_settlement_evidence();

CREATE TABLE railone.economic_fence_events (
    event_number bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    utt_id text NOT NULL REFERENCES railone.accepted_utts (utt_id),
    rtt_id text NOT NULL REFERENCES railone.rtt_attempts (rtt_id),
    fence_epoch bigint NOT NULL,
    event_type text NOT NULL CHECK (event_type IN (
        'RESERVED','PROVIDER_ACCEPTED','PROVIDER_REJECTED','PROVIDER_UNKNOWN',
        'VERIFIED_NO_EFFECT','SETTLED'
    )),
    evidence_id text,
    recorded_at timestamptz NOT NULL
);
CREATE INDEX economic_fence_events_utt_idx
    ON railone.economic_fence_events (utt_id, event_number);

CREATE TRIGGER economic_fence_evidence_immutable
BEFORE UPDATE OR DELETE ON railone.economic_fence_no_effect_evidence
FOR EACH ROW EXECUTE FUNCTION railone.reject_append_only_mutation();
CREATE TRIGGER economic_fence_events_immutable
BEFORE UPDATE OR DELETE ON railone.economic_fence_events
FOR EACH ROW EXECUTE FUNCTION railone.reject_append_only_mutation();

-- A bank principal maps an authenticated PostgreSQL login (session_user) to
-- one institution. The map is managed only by database security administrators.
CREATE TABLE railone.bank_analytics_principals (
    login_role name PRIMARY KEY,
    institution_id text NOT NULL REFERENCES railone.partner_institutions (institution_id),
    enabled boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Explicitly approved, low-resolution, bank-owned performance publications.
-- No route alternatives, rival-institution fields, pricing, raw identifiers or
-- source JSON may be placed in this structure.
CREATE TABLE railone.bank_analytics_publications (
    publication_id text PRIMARY KEY,
    institution_id text NOT NULL REFERENCES railone.partner_institutions (institution_id),
    metric_name text NOT NULL CHECK (metric_name IN (
        'OWN_UTT_SUBMITTED_TOTAL','OWN_UTT_SETTLED_TOTAL',
        'OWN_SETTLEMENT_LATENCY_P95_MS','OWN_PROVIDER_ACCEPTANCE_RATE_BPS'
    )),
    period_start timestamptz NOT NULL,
    period_end timestamptz NOT NULL,
    metric_value bigint NOT NULL CHECK (metric_value >= 0),
    sample_count bigint NOT NULL CHECK (sample_count >= 20),
    approved_by text NOT NULL CHECK (length(approved_by) BETWEEN 3 AND 128),
    published_at timestamptz NOT NULL DEFAULT now(),
    CHECK (period_end - period_start >= interval '1 day'),
    CHECK (metric_name <> 'OWN_PROVIDER_ACCEPTANCE_RATE_BPS' OR metric_value <= 10000),
    UNIQUE (institution_id, metric_name, period_start, period_end)
);
CREATE INDEX bank_analytics_publications_scope_idx
    ON railone.bank_analytics_publications (institution_id, period_end DESC);
CREATE TABLE railone.bank_analytics_withdrawals (
    publication_id text PRIMARY KEY REFERENCES railone.bank_analytics_publications (publication_id),
    reason_code text NOT NULL CHECK (reason_code IN ('CORRECTION','PRIVACY','POLICY')),
    withdrawn_at timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER bank_analytics_publications_immutable
BEFORE UPDATE OR DELETE ON railone.bank_analytics_publications
FOR EACH ROW EXECUTE FUNCTION railone.reject_append_only_mutation();
CREATE TRIGGER bank_analytics_withdrawals_immutable
BEFORE UPDATE OR DELETE ON railone.bank_analytics_withdrawals
FOR EACH ROW EXECUTE FUNCTION railone.reject_append_only_mutation();

CREATE SCHEMA railone_bank;
REVOKE ALL ON SCHEMA railone_bank FROM PUBLIC;
-- SECURITY DEFINER function does not accept caller-supplied institution IDs or GUCs.
-- SESSION_USER remains the actual DB login when a shared role is SET ROLE'd.
CREATE FUNCTION railone_bank.current_institution_id() RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog
AS $$
    SELECT p.institution_id
    FROM railone.bank_analytics_principals AS p
    WHERE p.login_role = session_user::name AND p.enabled IS TRUE
$$;
REVOKE ALL ON FUNCTION railone_bank.current_institution_id() FROM PUBLIC;

ALTER TABLE railone.bank_analytics_publications ENABLE ROW LEVEL SECURITY;
ALTER TABLE railone.bank_analytics_publications FORCE ROW LEVEL SECURITY;
CREATE POLICY bank_analytics_self_only ON railone.bank_analytics_publications
FOR SELECT USING (institution_id = railone_bank.current_institution_id());
-- A dedicated, authenticated publishing LOGIN is required. Membership in a
-- shared writer role is insufficient; a bank cannot SET ROLE to spoof SESSION_USER.
CREATE POLICY bank_analytics_publisher_insert ON railone.bank_analytics_publications
FOR INSERT WITH CHECK (session_user::text = 'railone_analytics_publisher');

CREATE VIEW railone_bank.metrics WITH (security_barrier=true) AS
SELECT p.metric_name, p.period_start, p.period_end,
       p.metric_value, p.sample_count
FROM railone.bank_analytics_publications AS p
WHERE p.institution_id = railone_bank.current_institution_id()
  AND NOT EXISTS (
      SELECT 1 FROM railone.bank_analytics_withdrawals AS w
      WHERE w.publication_id = p.publication_id
  );
REVOKE ALL ON railone_bank.metrics FROM PUBLIC;
-- Never grant raw railone schema access to any bank login.
REVOKE ALL ON SCHEMA railone FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA railone FROM PUBLIC;
-- Deployment administrators must deliberately grant only USAGE on railone_bank,
-- EXECUTE on current_institution_id(), and SELECT on railone_bank.metrics.

COMMIT;
