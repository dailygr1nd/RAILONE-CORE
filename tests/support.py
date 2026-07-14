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
