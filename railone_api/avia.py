"""Authenticated AviaOS merchant instruction intake for the institutional sandbox."""
import hashlib
import re

from railone_contracts import ContextType, OriginContext, PaymentPurpose, QuoteAcceptanceCommand
from railone_crypto.canonical_json import canonical_json_bytes
from .auth import PrincipalType
from .bilateral import _bounded, _envelope, _verify, _IDEMPOTENCY_KEY


PURPOSES = {"PAY_SUPPLIER": PaymentPurpose.SUPPLIER_PAYMENT,
            "BRANCH_FUND_TRANSFER": PaymentPurpose.BRANCH_FUND_TRANSFER}


def branch_permission(direction, merchant, branch, endpoint):
    """Issuer-provisioned grant for one institution/account binding at one branch."""
    digest = hashlib.sha256(canonical_json_bytes(
        [merchant, branch, endpoint["institution_id"], endpoint["account_binding_id"]])).hexdigest()
    return f"avia.{direction}.{digest}"


class AviaMerchantApi:
    def __init__(self, acceptance):
        self.acceptance = acceptance

    def create(self, principal, body, key, at):
        if principal.principal_type is not PrincipalType.MERCHANT_SERVICE:
            raise PermissionError("AVIA_MERCHANT_REQUIRED")
        _bounded(body)
        if set(body) != {"operation", "branch_id", "signed_quote", "origin_intent_id"}:
            raise PermissionError("INVALID_AVIA_REQUEST")
        def accept():
            op = body["operation"]
            purpose = PURPOSES[op]
            quote = _envelope(body, "signed_quote")
            payer, recipient = quote.payload["payer"], quote.payload["beneficiary"]
            merchant, branch = payer["actor_id"], body["branch_id"]
            permissions = principal.scopes.permissions
            if (not _IDEMPOTENCY_KEY.fullmatch(key) or
                    not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", body["origin_intent_id"]) or
                    principal.scopes.merchant_ids != (merchant,) or branch not in principal.scopes.branch_ids or
                    f"avia.{op}" not in permissions or payer["actor_type"] != "MERCHANT" or
                    quote.payload["purpose"] != purpose.value or
                    branch_permission("debit", merchant, branch, payer["endpoint"]) not in permissions):
                raise PermissionError("AVIA_SCOPE_MISMATCH")
            if op == "PAY_SUPPLIER":
                if recipient["actor_type"] != "SUPPLIER":
                    raise PermissionError("AVIA_SUPPLIER_REQUIRED")
            else:
                dest = recipient["actor_id"]
                if (recipient["actor_type"] != "BRANCH" or dest == branch or dest not in principal.scopes.branch_ids
                        or branch_permission("credit", merchant, dest, recipient["endpoint"]) not in permissions):
                    raise PermissionError("AVIA_DESTINATION_SCOPE_MISMATCH")
            origin = OriginContext("AVIA", body["origin_intent_id"], ContextType.MERCHANT, purpose,
                                   merchant_id=merchant, branch_id=branch)
            # Namespace the merchant's retry key away from human and other merchant keys.
            fingerprint = hashlib.sha256(canonical_json_bytes([merchant, branch, key])).hexdigest()
            return self.acceptance.accept(QuoteAcceptanceCommand(
                signed_quote=quote, origin=origin, idempotency_key="AVIA-"+fingerprint,
                authorization_method="MERCHANT_SERVICE", authorization_reference=principal.principal_id), at=at)
        result = _verify(accept)
        return {"utt_id": result.contract.utt_id, "status": "ACCEPTED", "replayed": result.replayed}
