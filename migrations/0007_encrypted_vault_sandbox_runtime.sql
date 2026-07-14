BEGIN;

CREATE TABLE railone.encrypted_secrets (
    vault_name text NOT NULL CHECK (
        vault_name IN (
            'ACCOUNT_ENDPOINT','CONTACT_DESTINATION',
            'PROVIDER_CREDENTIAL','NOTIFICATION_BODY'
        )
    ),
    record_id text NOT NULL,
    owner_id text NOT NULL,
    envelope jsonb NOT NULL,
    plaintext_sha256 char(64) NOT NULL CHECK (
        plaintext_sha256 ~ '^[0-9a-f]{64}$'
    ),
    encryption_key_id text NOT NULL,
    envelope_version integer NOT NULL CHECK (envelope_version = 1),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (vault_name, record_id),
    CHECK (envelope->>'algorithm' = 'A256GCM'),
    CHECK ((envelope->>'version')::integer = envelope_version),
    CHECK (envelope->>'key_id' = encryption_key_id),
    CHECK (envelope->>'purpose' = vault_name)
);

CREATE INDEX encrypted_secrets_owner_idx
    ON railone.encrypted_secrets (owner_id, vault_name);

CREATE TRIGGER encrypted_secrets_append_only
BEFORE UPDATE OR DELETE ON railone.encrypted_secrets
FOR EACH ROW EXECUTE FUNCTION railone.reject_append_only_mutation();

CREATE TABLE railone.sandbox_provider_effects (
    effect_id text PRIMARY KEY,
    provider_id text NOT NULL CHECK (provider_id IN ('BANK-KE','MPESA-KE')),
    rtt_id text NOT NULL REFERENCES railone.rtt_attempts (rtt_id),
    external_reference text NOT NULL,
    effect_type text NOT NULL CHECK (effect_type IN ('TIMEOUT','SETTLED','REJECTED')),
    provider_code text NOT NULL,
    due_tick bigint NOT NULL CHECK (due_tick >= 0),
    payload jsonb NOT NULL,
    payload_sha256 char(64) NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
    delivered_at timestamptz,
    version bigint NOT NULL DEFAULT 1 CHECK (version >= 1),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (provider_id, external_reference, effect_type)
);

CREATE INDEX sandbox_provider_effects_due_idx
    ON railone.sandbox_provider_effects (delivered_at, due_tick, effect_id);

CREATE FUNCTION railone.guard_sandbox_effect_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.effect_id <> OLD.effect_id
       OR NEW.provider_id <> OLD.provider_id
       OR NEW.rtt_id <> OLD.rtt_id
       OR NEW.external_reference <> OLD.external_reference
       OR NEW.effect_type <> OLD.effect_type
       OR NEW.provider_code <> OLD.provider_code
       OR NEW.due_tick <> OLD.due_tick
       OR NEW.payload <> OLD.payload
       OR NEW.payload_sha256 <> OLD.payload_sha256
       OR NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION 'sandbox provider effect birth material cannot change';
    END IF;
    IF OLD.delivered_at IS NOT NULL OR NEW.delivered_at IS NULL THEN
        RAISE EXCEPTION 'sandbox provider effect may be delivered exactly once';
    END IF;
    IF NEW.version <> OLD.version + 1 THEN
        RAISE EXCEPTION 'sandbox provider effect version must advance exactly once';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER sandbox_provider_effect_guarded_update
BEFORE UPDATE ON railone.sandbox_provider_effects
FOR EACH ROW EXECUTE FUNCTION railone.guard_sandbox_effect_update();

CREATE TRIGGER sandbox_provider_effect_no_delete
BEFORE DELETE ON railone.sandbox_provider_effects
FOR EACH ROW EXECUTE FUNCTION railone.reject_append_only_mutation();

COMMIT;
