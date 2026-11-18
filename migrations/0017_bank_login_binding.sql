BEGIN;

-- Existing mappings only identify a name. Require explicit re-enrolment
-- before granting a currently existing role that institution's publications.
ALTER TABLE railone.bank_analytics_principals ADD COLUMN login_oid oid;
UPDATE railone.bank_analytics_principals SET enabled = false WHERE enabled;
ALTER TABLE railone.bank_analytics_principals
    ADD CONSTRAINT enabled_bank_has_login_oid CHECK (NOT enabled OR login_oid IS NOT NULL);

CREATE FUNCTION railone.bind_bank_analytics_login() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF NEW.login_role IS DISTINCT FROM OLD.login_role
           OR NEW.login_oid IS DISTINCT FROM OLD.login_oid
           OR NEW.institution_id IS DISTINCT FROM OLD.institution_id THEN
            RAISE EXCEPTION 'replace the bank mapping to change its binding';
        END IF;
    END IF;
    IF NEW.enabled THEN
        SELECT r.oid INTO STRICT NEW.login_oid FROM pg_catalog.pg_roles r
        WHERE r.rolname = NEW.login_role AND r.rolcanlogin
          AND NOT r.rolsuper AND NOT r.rolbypassrls
          AND (NEW.login_oid IS NULL OR NEW.login_oid = r.oid);
    ELSIF TG_OP = 'INSERT' THEN
        NEW.login_oid := NULL;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER bank_analytics_login_binding
BEFORE INSERT OR UPDATE ON railone.bank_analytics_principals
FOR EACH ROW EXECUTE FUNCTION railone.bind_bank_analytics_login();

CREATE OR REPLACE FUNCTION railone_bank.current_institution_id() RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
    SELECT p.institution_id
    FROM railone.bank_analytics_principals p
    JOIN pg_catalog.pg_roles r ON r.oid = p.login_oid AND r.rolname = p.login_role
    JOIN railone.partner_institutions i ON i.institution_id = p.institution_id
    WHERE r.rolname = session_user AND r.rolcanlogin AND NOT r.rolsuper AND NOT r.rolbypassrls
      AND p.enabled AND i.status = 'ACTIVE'
$$;
COMMIT;
