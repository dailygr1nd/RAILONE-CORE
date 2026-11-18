"""Beneficiary-signed, per-transfer inbound mandates for destination institutions."""
from datetime import datetime
from uuid import uuid4

from railone_crypto.signature_service import ArtifactType, SignatureEnvelope

MODE = "BENEFICIARY_PREAUTHORIZED"


def grant(signatures, *, beneficiary, institution, account_binding_id, currency,
          max_receive_minor, issued_at: datetime, expires_at: datetime, signing_key_id):
    if (issued_at.tzinfo is None or expires_at.tzinfo is None
            or int(expires_at.timestamp()) <= int(issued_at.timestamp())
            or type(max_receive_minor) is not int or max_receive_minor <= 0):
        raise ValueError("invalid mandate limit or validity")
    body = dict(version=1, mandate_id=uuid4().hex, beneficiary=beneficiary,
                institution=institution, account_binding_id=account_binding_id,
                currency=currency, max_receive_minor=max_receive_minor,
                expires_at=int(expires_at.timestamp()))
    signature = signatures.sign_artifact(artifact_type=ArtifactType.RECEIVE_MANDATE,
        payload=body, key_id=signing_key_id, issued_at=issued_at)
    verify_grant(signatures, signature)
    return signature


def verify_grant(signatures, mandate):
    p = mandate.payload
    fields = {"version", "mandate_id", "beneficiary", "institution", "account_binding_id",
              "currency", "max_receive_minor", "expires_at"}
    if (not signatures.verify_artifact(mandate, expected_artifact_type=ArtifactType.RECEIVE_MANDATE).valid
            or set(p) != fields or type(p["version"]) is not int or p["version"] != 1
            or any(not isinstance(p[k], str) or not p[k].strip()
                   for k in ("mandate_id", "beneficiary", "institution", "account_binding_id", "currency"))
            or mandate.protected["iss"] != p["beneficiary"]
            or type(p["expires_at"]) is not int or p["expires_at"] <= mandate.protected["iat"]
            or type(p["max_receive_minor"]) is not int or p["max_receive_minor"] <= 0):
        raise PermissionError("MANDATE_INVALID")


def receiver_owner(signatures, receiver, terms, *, sender_epoch, check_epoch):
    mode = receiver.get("participation_mode")
    if mode == "ACTIVE_ACCEPTANCE" and receiver.get("receiver_confirmed") is True and "mandate" not in receiver:
        return terms["beneficiary"]["actor_id"]
    if mode != MODE or receiver.get("receiver_confirmed") is not False:
        raise PermissionError("INVALID_RECEIVER_MODE")
    try:
        mandate = SignatureEnvelope.from_dict(receiver["mandate"])
    except (AttributeError, KeyError, ValueError, TypeError) as exc:
        raise PermissionError("MANDATE_INVALID") from exc
    verify_grant(signatures, mandate)
    p = mandate.payload
    beneficiary = terms["beneficiary"]
    endpoint = beneficiary["endpoint"]
    if ((p["beneficiary"], p["institution"], p["account_binding_id"], p["currency"])
            != (beneficiary["actor_id"], endpoint["institution_id"], endpoint["account_binding_id"], terms["currency_to"])
            or terms["receive_amount_minor"] > p["max_receive_minor"]
            or not mandate.protected["iat"] <= sender_epoch <= check_epoch < p["expires_at"]):
        raise PermissionError("MANDATE_OUTSIDE_SCOPE")
    return p["institution"]
