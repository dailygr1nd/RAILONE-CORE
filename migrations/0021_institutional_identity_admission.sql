BEGIN;

-- R1-IOS-001: legal identity is separate from ACTIVE partners and signed adapter manifests.
-- The onboarding service verifies trust signatures; this private table is not a network permission.
CREATE TABLE railone.institution_identity_registry (
    institution_id text PRIMARY KEY CHECK (
        institution_id ~ '^INST-[A-Z]{2}-(BNK|MNO|PSP|AGG|SWI|EMI)-[A-Z2-7]{16}$'),
    legal_name text NOT NULL CHECK (length(btrim(legal_name)) BETWEEN 2 AND 160),
    display_name text NOT NULL CHECK (length(btrim(display_name)) BETWEEN 2 AND 160),
    institution_class text NOT NULL CHECK (institution_class IN ('BNK','MNO','PSP','AGG','SWI','EMI')),
    home_jurisdiction char(2) NOT NULL CHECK (home_jurisdiction ~ '^[A-Z]{2}$'),
    registration_reference text NOT NULL,
    regulatory_evidence_refs text[] NOT NULL CHECK (cardinality(regulatory_evidence_refs) BETWEEN 1 AND 20),
    identity_state text NOT NULL DEFAULT 'PENDING_VERIFICATION'
        CHECK (identity_state IN ('PENDING_VERIFICATION','VERIFIED')),
    submitted_at timestamptz NOT NULL,
    verified_at timestamptz,
    signed_verification jsonb,
    UNIQUE (home_jurisdiction, registration_reference),
    CONSTRAINT identity_verification_pair CHECK (
        (identity_state = 'PENDING_VERIFICATION' AND verified_at IS NULL AND signed_verification IS NULL)
        OR (identity_state = 'VERIFIED' AND verified_at IS NOT NULL AND signed_verification IS NOT NULL)
    )
);

CREATE TABLE railone.institution_identity_verification_events (
    event_sha256 char(64) PRIMARY KEY CHECK (event_sha256 ~ '^[0-9a-f]{64}$'),
    institution_id text NOT NULL REFERENCES railone.institution_identity_registry(institution_id),
    signed_verification jsonb NOT NULL,
    recorded_at timestamptz NOT NULL
);

CREATE OR REPLACE FUNCTION railone.guard_institution_identity_update() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'institutional identity is not deletable';
    END IF;
    IF ROW(NEW.institution_id,NEW.legal_name,NEW.display_name,NEW.institution_class,
           NEW.home_jurisdiction,NEW.registration_reference,NEW.regulatory_evidence_refs,
           NEW.submitted_at) IS DISTINCT FROM
       ROW(OLD.institution_id,OLD.legal_name,OLD.display_name,OLD.institution_class,
           OLD.home_jurisdiction,OLD.registration_reference,OLD.regulatory_evidence_refs,
           OLD.submitted_at) THEN
        RAISE EXCEPTION 'institutional registration provenance is immutable';
    END IF;
    IF OLD.identity_state <> 'PENDING_VERIFICATION' OR NEW.identity_state <> 'VERIFIED'
       OR OLD.signed_verification IS NOT NULL OR NEW.signed_verification IS NULL
       OR NEW.verified_at IS NULL THEN
        RAISE EXCEPTION 'institutional verification state cannot be rewritten';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER guard_institution_identity_update
BEFORE UPDATE OR DELETE ON railone.institution_identity_registry
FOR EACH ROW EXECUTE FUNCTION railone.guard_institution_identity_update();

CREATE OR REPLACE FUNCTION railone.guard_institution_verification_event() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'institution verification evidence is append-only';
END;
$$;
CREATE TRIGGER guard_institution_verification_event
BEFORE UPDATE OR DELETE ON railone.institution_identity_verification_events
FOR EACH ROW EXECUTE FUNCTION railone.guard_institution_verification_event();

-- Neither partner logins nor PUBLIC may access the private onboarding registry.
REVOKE ALL ON railone.institution_identity_registry FROM PUBLIC;
REVOKE ALL ON railone.institution_identity_verification_events FROM PUBLIC;

COMMIT;
