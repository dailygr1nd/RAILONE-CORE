BEGIN;

CREATE TABLE railone.partner_institutions (
    institution_id text PRIMARY KEY,
    display_name text NOT NULL,
    country_codes text[] NOT NULL,
    currencies text[] NOT NULL,
    supported_roles text[] NOT NULL,
    status text NOT NULL CHECK (status IN ('ACTIVE','PAUSED','OFFBOARDED')),
    version bigint NOT NULL DEFAULT 1 CHECK (version >= 1),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE TABLE railone.account_bindings (
    account_binding_id text PRIMARY KEY,
    actor_id text NOT NULL,
    institution_id text NOT NULL REFERENCES railone.partner_institutions (institution_id),
    role text NOT NULL CHECK (role IN ('DEBIT','CREDIT')),
    account_type text NOT NULL CHECK (
        account_type IN ('BANK_ACCOUNT','MOBILE_MONEY','WALLET','CARD_ACCOUNT')
    ),
    currency char(3) NOT NULL,
    display_hint text NOT NULL CHECK (length(display_hint) <= 32),
    contact_binding_id text NOT NULL,
    attestation_reference text NOT NULL,
    status text NOT NULL CHECK (status IN ('ACTIVE','REVOKED','SUSPENDED')),
    version bigint NOT NULL DEFAULT 1 CHECK (version >= 1),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    UNIQUE (actor_id, institution_id, account_binding_id)
);

COMMENT ON TABLE railone.account_bindings IS
    'Opaque institution account bindings only; raw account, wallet, card and MSISDN endpoints are prohibited';

CREATE INDEX account_bindings_actor_idx
    ON railone.account_bindings (actor_id, status, institution_id, role);

CREATE FUNCTION railone.guard_partner_institution_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.institution_id <> OLD.institution_id OR NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION 'partner institution identity cannot change';
    END IF;
    IF NEW.version <> OLD.version + 1 THEN
        RAISE EXCEPTION 'partner institution version must advance exactly once';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER partner_institution_guarded_update
BEFORE UPDATE ON railone.partner_institutions
FOR EACH ROW EXECUTE FUNCTION railone.guard_partner_institution_update();

CREATE TRIGGER partner_institution_no_delete
BEFORE DELETE ON railone.partner_institutions
FOR EACH ROW EXECUTE FUNCTION railone.reject_append_only_mutation();

CREATE FUNCTION railone.guard_account_binding_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.account_binding_id <> OLD.account_binding_id
       OR NEW.actor_id <> OLD.actor_id
       OR NEW.institution_id <> OLD.institution_id
       OR NEW.role <> OLD.role
       OR NEW.account_type <> OLD.account_type
       OR NEW.currency <> OLD.currency
       OR NEW.display_hint <> OLD.display_hint
       OR NEW.contact_binding_id <> OLD.contact_binding_id
       OR NEW.attestation_reference <> OLD.attestation_reference
       OR NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION 'account binding identity and attestation cannot change';
    END IF;
    IF NEW.version <> OLD.version + 1 THEN
        RAISE EXCEPTION 'account binding version must advance exactly once';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER account_binding_guarded_update
BEFORE UPDATE ON railone.account_bindings
FOR EACH ROW EXECUTE FUNCTION railone.guard_account_binding_update();

CREATE TRIGGER account_binding_no_delete
BEFORE DELETE ON railone.account_bindings
FOR EACH ROW EXECUTE FUNCTION railone.reject_append_only_mutation();

CREATE TABLE railone.settlement_evidence (
    evidence_id text PRIMARY KEY,
    utt_id text NOT NULL UNIQUE REFERENCES railone.accepted_utts (utt_id),
    provider_id text NOT NULL,
    provider_transaction_id text NOT NULL,
    callback_event_id text NOT NULL,
    signed_evidence jsonb NOT NULL,
    evidence_payload_sha256 char(64) NOT NULL CHECK (
        evidence_payload_sha256 ~ '^[0-9a-f]{64}$'
    ),
    settled_at timestamptz NOT NULL,
    UNIQUE (provider_id, provider_transaction_id)
);

CREATE TABLE railone.sms_notification_outbox (
    notification_id text PRIMARY KEY,
    evidence_id text NOT NULL REFERENCES railone.settlement_evidence (evidence_id),
    utt_id text NOT NULL REFERENCES railone.accepted_utts (utt_id),
    recipient_role text NOT NULL CHECK (recipient_role IN ('SENDER','RECEIVER')),
    contact_binding_id text NOT NULL,
    template_version text NOT NULL,
    rendered_body text NOT NULL CHECK (length(rendered_body) <= 320),
    body_sha256 char(64) NOT NULL CHECK (body_sha256 ~ '^[0-9a-f]{64}$'),
    state text NOT NULL CHECK (
        state IN ('PREPARED','DISPATCHING','SENT','REJECTED','UNKNOWN')
    ),
    gateway_reference text,
    normalized_code text,
    version bigint NOT NULL DEFAULT 1 CHECK (version >= 1),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    UNIQUE (evidence_id, recipient_role, template_version)
);

CREATE INDEX sms_notification_pending_idx
    ON railone.sms_notification_outbox (state, created_at, notification_id);

CREATE TRIGGER settlement_evidence_append_only
BEFORE UPDATE OR DELETE ON railone.settlement_evidence
FOR EACH ROW EXECUTE FUNCTION railone.reject_append_only_mutation();

CREATE FUNCTION railone.guard_sms_notification_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.notification_id <> OLD.notification_id
       OR NEW.evidence_id <> OLD.evidence_id
       OR NEW.utt_id <> OLD.utt_id
       OR NEW.recipient_role <> OLD.recipient_role
       OR NEW.contact_binding_id <> OLD.contact_binding_id
       OR NEW.template_version <> OLD.template_version
       OR NEW.rendered_body <> OLD.rendered_body
       OR NEW.body_sha256 <> OLD.body_sha256
       OR NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION 'SMS notification birth material cannot change';
    END IF;
    IF NEW.version <> OLD.version + 1 THEN
        RAISE EXCEPTION 'SMS notification version must advance exactly once';
    END IF;
    IF OLD.state = 'PREPARED' AND NEW.state <> 'DISPATCHING' THEN
        RAISE EXCEPTION 'prepared SMS must enter dispatching before an outcome';
    END IF;
    IF OLD.state = 'DISPATCHING'
       AND NEW.state NOT IN ('SENT','REJECTED','UNKNOWN') THEN
        RAISE EXCEPTION 'dispatching SMS requires a terminal delivery outcome';
    END IF;
    IF OLD.state IN ('SENT','REJECTED','UNKNOWN') THEN
        RAISE EXCEPTION 'SMS delivery outcome is terminal';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER sms_notification_guarded_update
BEFORE UPDATE ON railone.sms_notification_outbox
FOR EACH ROW EXECUTE FUNCTION railone.guard_sms_notification_update();

CREATE TRIGGER sms_notification_no_delete
BEFORE DELETE ON railone.sms_notification_outbox
FOR EACH ROW EXECUTE FUNCTION railone.reject_append_only_mutation();

COMMIT;
