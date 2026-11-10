-- Forward-only confidentiality hardening: the raw plaintext hash is unnecessary.
-- It permits offline guessing of predictable account/contact values after a DB leak.
-- AES-GCM already authenticates the encrypted envelope; no digest replacement is needed.
-- Existing hashes in old backups, replicas and dumps require separate retention review.
BEGIN;
ALTER TABLE railone.encrypted_secrets
    DROP COLUMN plaintext_sha256;
COMMIT;
