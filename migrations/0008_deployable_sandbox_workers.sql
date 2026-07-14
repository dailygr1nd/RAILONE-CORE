BEGIN;

ALTER TABLE railone.sms_notification_outbox
    ADD COLUMN rendered_body_envelope jsonb,
    ADD COLUMN body_encryption_key_id text,
    ADD COLUMN body_envelope_version integer;

ALTER TABLE railone.sms_notification_outbox
    ADD CONSTRAINT sms_notification_body_storage_check CHECK (
        (
            rendered_body = '[ENCRYPTED]'
            AND rendered_body_envelope IS NOT NULL
            AND body_encryption_key_id IS NOT NULL
            AND body_envelope_version = 1
            AND rendered_body_envelope->>'algorithm' = 'A256GCM'
            AND rendered_body_envelope->>'purpose' = 'NOTIFICATION_BODY'
            AND rendered_body_envelope->>'key_id' = body_encryption_key_id
        )
        OR
        (
            rendered_body <> '[ENCRYPTED]'
            AND rendered_body_envelope IS NULL
            AND body_encryption_key_id IS NULL
            AND body_envelope_version IS NULL
        )
    );

CREATE OR REPLACE FUNCTION railone.guard_sms_notification_update()
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
       OR NEW.rendered_body_envelope IS DISTINCT FROM OLD.rendered_body_envelope
       OR NEW.body_encryption_key_id IS DISTINCT FROM OLD.body_encryption_key_id
       OR NEW.body_envelope_version IS DISTINCT FROM OLD.body_envelope_version
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

ALTER TABLE railone.sandbox_provider_effects
    ADD COLUMN delivery_state text NOT NULL DEFAULT 'PENDING' CHECK (
        delivery_state IN ('PENDING','IN_FLIGHT','DELIVERED','DEAD_LETTER')
    ),
    ADD COLUMN delivery_attempts integer NOT NULL DEFAULT 0 CHECK (
        delivery_attempts >= 0
    ),
    ADD COLUMN lease_owner text,
    ADD COLUMN lease_until_tick bigint,
    ADD COLUMN last_error text,
    ADD COLUMN delivered_at_tick bigint;

ALTER TABLE railone.sandbox_provider_effects
    ADD COLUMN available_tick bigint;
UPDATE railone.sandbox_provider_effects SET available_tick = due_tick;
ALTER TABLE railone.sandbox_provider_effects
    ALTER COLUMN available_tick SET NOT NULL,
    ADD CONSTRAINT sandbox_effect_available_tick_check CHECK (available_tick >= 0);

CREATE TABLE railone.sandbox_runtime_clock (
    clock_id boolean PRIMARY KEY DEFAULT true CHECK (clock_id),
    current_tick bigint NOT NULL DEFAULT 0 CHECK (current_tick >= 0),
    version bigint NOT NULL DEFAULT 1 CHECK (version >= 1),
    updated_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO railone.sandbox_runtime_clock (clock_id) VALUES (true)
ON CONFLICT (clock_id) DO NOTHING;

CREATE OR REPLACE FUNCTION railone.guard_sandbox_effect_update()
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
    IF NEW.version <> OLD.version + 1 THEN
        RAISE EXCEPTION 'sandbox provider effect version must advance exactly once';
    END IF;
    IF OLD.delivery_state = 'PENDING'
       AND NEW.delivery_state <> 'IN_FLIGHT'
       AND NOT (
           OLD.delivered_at IS NOT NULL
           AND NEW.delivery_state = 'DELIVERED'
       ) THEN
        RAISE EXCEPTION 'pending sandbox effect must be claimed';
    END IF;
    IF OLD.delivery_state = 'IN_FLIGHT'
       AND NEW.delivery_state NOT IN ('IN_FLIGHT','PENDING','DELIVERED','DEAD_LETTER') THEN
        RAISE EXCEPTION 'invalid sandbox effect delivery transition';
    END IF;
    IF OLD.delivery_state IN ('DELIVERED','DEAD_LETTER') THEN
        RAISE EXCEPTION 'sandbox effect delivery outcome is terminal';
    END IF;
    IF NEW.delivery_state = 'IN_FLIGHT'
       AND (NEW.lease_owner IS NULL OR NEW.lease_until_tick IS NULL) THEN
        RAISE EXCEPTION 'claimed sandbox effect requires a lease';
    END IF;
    IF NEW.delivery_state <> 'IN_FLIGHT'
       AND (NEW.lease_owner IS NOT NULL OR NEW.lease_until_tick IS NOT NULL) THEN
        RAISE EXCEPTION 'unclaimed sandbox effect cannot retain a lease';
    END IF;
    IF NEW.delivery_state = 'DELIVERED'
       AND (NEW.delivered_at IS NULL OR NEW.delivered_at_tick IS NULL) THEN
        RAISE EXCEPTION 'delivered sandbox effect requires delivery time';
    END IF;
    RETURN NEW;
END;
$$;

-- Preserve effects delivered by the Step 11B inline scheduler before delivery
-- state and leases existed.
UPDATE railone.sandbox_provider_effects
SET delivery_state = 'DELIVERED',
    delivery_attempts = GREATEST(delivery_attempts, 1),
    delivered_at_tick = due_tick,
    version = version + 1
WHERE delivered_at IS NOT NULL;

DROP INDEX railone.sandbox_provider_effects_due_idx;
CREATE INDEX sandbox_provider_effects_due_idx
    ON railone.sandbox_provider_effects
    (delivery_state, available_tick, lease_until_tick, effect_id);

COMMIT;
