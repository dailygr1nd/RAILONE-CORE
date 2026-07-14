BEGIN;

CREATE SCHEMA IF NOT EXISTS railone;

CREATE TABLE railone.identity_genesis (
    rig_id text PRIMARY KEY,
    continuity_uid text NOT NULL UNIQUE CHECK (continuity_uid ~ '^CUID-[A-Z2-7]{32}$'),
    continuity_key_id text NOT NULL,
    identity_fingerprint char(64) NOT NULL UNIQUE CHECK (identity_fingerprint ~ '^[0-9a-f]{64}$'),
    verification_provider_id text NOT NULL,
    verification_reference text NOT NULL,
    evidence_sha256 char(64) NOT NULL CHECK (evidence_sha256 ~ '^[0-9a-f]{64}$'),
    attestation_id text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL
);

CREATE TABLE railone.identity_objects (
    rio_id text PRIMARY KEY,
    railone_id text NOT NULL UNIQUE,
    continuity_uid text NOT NULL UNIQUE
        REFERENCES railone.identity_genesis (continuity_uid),
    rig_id text NOT NULL UNIQUE REFERENCES railone.identity_genesis (rig_id),
    active_riv_id text NOT NULL,
    active_revision bigint NOT NULL CHECK (active_revision >= 1),
    corridor text NOT NULL,
    status text NOT NULL CHECK (
        status IN ('ACTIVE', 'REVERIFICATION_REQUIRED', 'SUSPENDED', 'REVOKED')
    ),
    projection_version bigint NOT NULL DEFAULT 1 CHECK (projection_version >= 1),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE TABLE railone.identity_revisions (
    riv_id text PRIMARY KEY,
    rio_id text NOT NULL REFERENCES railone.identity_objects (rio_id),
    continuity_uid text NOT NULL REFERENCES railone.identity_genesis (continuity_uid),
    revision bigint NOT NULL CHECK (revision >= 1),
    trust_tier text NOT NULL CHECK (trust_tier IN ('T0', 'T1', 'T2', 'T3', 'T4', 'T5')),
    status text NOT NULL CHECK (
        status IN ('ACTIVE', 'REVERIFICATION_REQUIRED', 'SUSPENDED', 'REVOKED')
    ),
    reason text NOT NULL,
    attestation_id text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL,
    UNIQUE (continuity_uid, revision),
    UNIQUE (rio_id, revision),
    UNIQUE (riv_id, rio_id)
);

ALTER TABLE railone.identity_objects
    ADD CONSTRAINT identity_objects_active_riv_fk
    FOREIGN KEY (active_riv_id, rio_id)
    REFERENCES railone.identity_revisions (riv_id, rio_id)
    DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE railone.accepted_utts (
    utt_id text PRIMARY KEY CHECK (utt_id ~ '^UTT-[A-F0-9]{32}$'),
    quote_id text NOT NULL UNIQUE,
    utt_payload_sha256 char(64) NOT NULL UNIQUE CHECK (utt_payload_sha256 ~ '^[0-9a-f]{64}$'),
    signed_envelope jsonb NOT NULL,
    accepted_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE railone.utt_transaction_projections (
    utt_id text PRIMARY KEY REFERENCES railone.accepted_utts (utt_id),
    utt_payload_sha256 char(64) NOT NULL,
    quote_id text NOT NULL,
    purpose text NOT NULL,
    context_type text NOT NULL CHECK (context_type IN ('P2P', 'MERCHANT', 'PARTNER')),
    amount_minor bigint NOT NULL CHECK (amount_minor > 0),
    currency_from char(3) NOT NULL,
    receive_amount_minor bigint NOT NULL CHECK (receive_amount_minor > 0),
    currency_to char(3) NOT NULL,
    commercial_state text NOT NULL,
    accepted_at timestamptz NOT NULL,
    indexed_at timestamptz NOT NULL,
    FOREIGN KEY (utt_payload_sha256)
        REFERENCES railone.accepted_utts (utt_payload_sha256)
);

CREATE TABLE railone.utt_subject_links (
    utt_id text NOT NULL REFERENCES railone.utt_transaction_projections (utt_id),
    subject_kind text NOT NULL CHECK (
        subject_kind IN ('CONTINUITY_UID', 'MERCHANT_ID', 'BRANCH_ID', 'PARTNER_ID')
    ),
    subject_id text NOT NULL,
    continuity_uid text GENERATED ALWAYS AS (
        CASE WHEN subject_kind = 'CONTINUITY_UID' THEN subject_id ELSE NULL END
    ) STORED REFERENCES railone.identity_genesis (continuity_uid),
    roles text[] NOT NULL CHECK (
        cardinality(roles) > 0
        AND roles <@ ARRAY[
            'PAYER', 'BENEFICIARY', 'AUTHORIZER',
            'ORIGIN_MERCHANT', 'ORIGIN_BRANCH', 'ORIGIN_PARTNER'
        ]::text[]
    ),
    linked_at timestamptz NOT NULL,
    CHECK (subject_id = upper(subject_id)),
    PRIMARY KEY (utt_id, subject_kind, subject_id)
);

CREATE INDEX utt_subject_links_subject_history_idx
    ON railone.utt_subject_links (subject_kind, subject_id, utt_id);

CREATE INDEX utt_transaction_projections_history_idx
    ON railone.utt_transaction_projections (accepted_at DESC, utt_id DESC);

CREATE TABLE railone.transaction_access_audit (
    audit_id text PRIMARY KEY,
    principal_id text NOT NULL,
    target_kind text NOT NULL,
    target_id text NOT NULL,
    outcome text NOT NULL CHECK (outcome IN ('ALLOWED', 'DENIED')),
    access_reason text NOT NULL,
    occurred_at timestamptz NOT NULL
);

CREATE INDEX transaction_access_audit_principal_idx
    ON railone.transaction_access_audit (principal_id, occurred_at DESC);

CREATE FUNCTION railone.reject_append_only_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
END;
$$;

CREATE TRIGGER identity_genesis_append_only
BEFORE UPDATE OR DELETE ON railone.identity_genesis
FOR EACH ROW EXECUTE FUNCTION railone.reject_append_only_mutation();

CREATE TRIGGER identity_revisions_append_only
BEFORE UPDATE OR DELETE ON railone.identity_revisions
FOR EACH ROW EXECUTE FUNCTION railone.reject_append_only_mutation();

CREATE TRIGGER accepted_utts_append_only
BEFORE UPDATE OR DELETE ON railone.accepted_utts
FOR EACH ROW EXECUTE FUNCTION railone.reject_append_only_mutation();

CREATE TRIGGER utt_transaction_projections_append_only
BEFORE UPDATE OR DELETE ON railone.utt_transaction_projections
FOR EACH ROW EXECUTE FUNCTION railone.reject_append_only_mutation();

CREATE TRIGGER utt_subject_links_append_only
BEFORE UPDATE OR DELETE ON railone.utt_subject_links
FOR EACH ROW EXECUTE FUNCTION railone.reject_append_only_mutation();

CREATE TRIGGER transaction_access_audit_append_only
BEFORE UPDATE OR DELETE ON railone.transaction_access_audit
FOR EACH ROW EXECUTE FUNCTION railone.reject_append_only_mutation();

CREATE FUNCTION railone.guard_identity_projection_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.rio_id <> OLD.rio_id
       OR NEW.railone_id <> OLD.railone_id
       OR NEW.continuity_uid <> OLD.continuity_uid
       OR NEW.rig_id <> OLD.rig_id
       OR NEW.corridor <> OLD.corridor
       OR NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION 'immutable identity projection fields cannot change';
    END IF;
    IF NEW.projection_version <> OLD.projection_version + 1 THEN
        RAISE EXCEPTION 'identity projection version must advance exactly once';
    END IF;
    IF OLD.status = 'REVOKED' THEN
        RAISE EXCEPTION 'revoked identity cannot transition';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER identity_objects_guarded_update
BEFORE UPDATE ON railone.identity_objects
FOR EACH ROW EXECUTE FUNCTION railone.guard_identity_projection_update();

CREATE TRIGGER identity_objects_no_delete
BEFORE DELETE ON railone.identity_objects
FOR EACH ROW EXECUTE FUNCTION railone.reject_append_only_mutation();

CREATE FUNCTION railone.assert_identity_projection_consistency()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM railone.identity_revisions revision
        WHERE revision.riv_id = NEW.active_riv_id
          AND revision.rio_id = NEW.rio_id
          AND revision.continuity_uid = NEW.continuity_uid
          AND revision.revision = NEW.active_revision
          AND revision.status = NEW.status
    ) THEN
        RAISE EXCEPTION 'active identity revision does not match identity projection';
    END IF;
    RETURN NEW;
END;
$$;

CREATE CONSTRAINT TRIGGER identity_objects_revision_consistency
AFTER INSERT OR UPDATE ON railone.identity_objects
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION railone.assert_identity_projection_consistency();

COMMIT;
