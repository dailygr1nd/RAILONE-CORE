# v0.18 sandbox decision — beneficiary verification before ETK-S

The strict P2P path uses authority format 4. Before signing ETK-S the sender checks a destination institution's Ed25519 verification envelope. Provision the institution's verification public key under its trusted institution ID with the dedicated BENEFICIARY_VERIFICATION purpose. Only a successful identity-and-account match may produce this artifact. The sandbox uses synthetic directory evidence. Real adapters must perform the underlying lookup and retain the supporting record.

The evidence payload carries version 1, result IDENTITY_AND_ACCOUNT_MATCH, an opaque verification_ref, quote_id, beneficiary_actor_id, destination_sha256 (canonical JSON digest of the complete credit endpoint), currency and expires_at. The protected signature header supplies issuer and issuance time. The maximum evidence lifetime follows the sandbox's existing 900-second authority ceiling. The proof must be valid when signing ETK-S and at admission through UTT creation. Execution checks freshness at the UTT acceptance timestamp and continues to enforce current bilateral authority windows and key revocation.

The signed institution evidence is embedded in ETK-S and persisted in the existing authority envelope. ETK-R binds the ETK-S digest. The signed UTT pins both authorities. PostgreSQL requires no schema migration. No new settlement or retry semantics are introduced.

Format 3 records remain readable. Existing signed version 3 authorizations cannot be promoted into version 4 or dispatched on the upgraded institutional path. Drain or reconcile in-flight attempts before cutover. Uncertain economic effects require reconciliation before requesting fresh authorization. The historical v1 compatibility path is outside this strict profile. Deploy the institutional composition with sender-first enforcement enabled.

Validation uses the authenticated HTTP sandbox and a disposable PostgreSQL database. Negative cases cover missing evidence, other institution, wrong actor or endpoint, account-existence-only result, wrong quote, expired evidence, and sender re-signing a payload without the proof.
