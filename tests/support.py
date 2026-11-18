from __future__ import annotations

from railone_contracts import AccountEndpoint, AccountRole, AccountType, QuoteService


def endpoint(
    binding_id: str,
    role: AccountRole,
    *,
    institution_id: str | None = None,
    account_type: AccountType = AccountType.BANK_ACCOUNT,
    display_hint: str | None = None,
    contact_binding_id: str | None = None,
) -> AccountEndpoint:
    institution = institution_id or (
        "INST-SOURCE" if role is AccountRole.DEBIT else "INST-DEST"
    )
    return AccountEndpoint(
        institution_id=institution,
        institution_display_name=institution,
        account_binding_id=binding_id,
        role=role,
        account_type=account_type,
        display_hint=display_hint or ("****1111" if role is AccountRole.DEBIT else "****2222"),
        contact_binding_id=contact_binding_id or f"CONTACT-{binding_id}",
        attestation_reference=f"ATTEST-{binding_id}",
    )


def quote_service(signatures) -> QuoteService:
    return QuoteService(signatures, allow_unverified_endpoints_for_tests=True)


def beneficiary_evidence(signatures, quote, at, **changes):
    """Simulate a destination institution's affirmative directory response."""
    import hashlib
    from railone_crypto.canonical_json import canonical_json_bytes
    from railone_crypto.signature_service import ArtifactType
    beneficiary = quote.payload["beneficiary"]
    payload = {
        "version": 1, "result": "IDENTITY_AND_ACCOUNT_MATCH",
        "verification_ref": "SYNTHETIC-MATCH", "quote_id": quote.payload["quote_id"],
        "beneficiary_actor_id": beneficiary["actor_id"],
        "destination_sha256": hashlib.sha256(canonical_json_bytes(beneficiary["endpoint"])).hexdigest(),
        "currency": quote.payload["currency_to"], "expires_at": int(at.timestamp()) + 120,
        **changes,
    }
    return signatures.sign_artifact(artifact_type=ArtifactType.BENEFICIARY_VERIFICATION,
                                    payload=payload, key_id="fixture-destination-verifier", issued_at=at)
