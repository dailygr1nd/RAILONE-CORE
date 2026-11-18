BEGIN;
CREATE TABLE railone.receiving_mandates (
    mandate_id text PRIMARY KEY,
    signed_grant jsonb NOT NULL,
    revoked_at timestamptz,
    CHECK ((signed_grant #>> '{payload,mandate_id}') IS NOT DISTINCT FROM mandate_id)
);
CREATE FUNCTION railone.guard_receiving_mandate() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.revoked_at IS NOT NULL OR NEW.revoked_at IS NULL
       OR NEW.signed_grant IS DISTINCT FROM OLD.signed_grant
       OR NEW.mandate_id IS DISTINCT FROM OLD.mandate_id THEN
        RAISE EXCEPTION 'mandate permits only terminal revocation';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER receiving_mandate_guard BEFORE UPDATE ON railone.receiving_mandates
FOR EACH ROW EXECUTE FUNCTION railone.guard_receiving_mandate();
CREATE TRIGGER receiving_mandate_no_delete BEFORE DELETE ON railone.receiving_mandates
FOR EACH ROW EXECUTE FUNCTION railone.reject_append_only_mutation();
REVOKE ALL ON railone.receiving_mandates FROM PUBLIC;
COMMIT;
