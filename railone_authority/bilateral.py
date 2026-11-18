"""Sender-first bilateral authority for P2P sandbox execution, version 4.

The sender signs the immutable quote commitment first. The receiver then signs
an acceptance that binds to the exact ETK-S digest. RailOne verifies both
authorities before UTT creation; neither pre-UTT authority includes a UTT ID.
"""

from __future__ import annotations

import hashlib
from .mandates import MODE, receiver_owner
from datetime import datetime
from typing import Mapping, Any

from railone_crypto.canonical_json import canonical_json_bytes
from railone_crypto.signature_service import ArtifactType, SignatureEnvelope, SignatureService


def _sha(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _id(prefix: str, value: Mapping[str, Any]) -> str:
    return prefix + "-" + _sha(value)[:32].upper()


def _instant(at: datetime) -> int:
    if at.tzinfo is None:
        raise ValueError("authority time must be timezone-aware")
    return int(at.timestamp())


def _verified(signatures: SignatureService, envelope: SignatureEnvelope, kind: ArtifactType, owner: str) -> Mapping[str, Any]:
    check = signatures.verify_artifact(envelope, expected_artifact_type=kind)
    if not check.valid:
        raise PermissionError("BILATERAL_SIGNATURE_INVALID:" + check.reason)
    if envelope.protected.get("iss") != owner:
        raise PermissionError("BILATERAL_SIGNER_OWNER_MISMATCH")
    return envelope.payload


def quote_commitment(quote: Mapping[str, Any]) -> dict[str, Any]:
    """Bind all quote terms, not merely the amount or visible account aliases."""
    return {
        "quote_id": quote["quote_id"],
        "quote_payload_sha256": quote.get("quote_payload_sha256") or _sha(quote),
        "payer_actor_id": quote["payer"]["actor_id"],
        "payer_actor_type": quote["payer"]["actor_type"],
        "beneficiary_actor_id": quote["beneficiary"]["actor_id"],
        "beneficiary_actor_type": quote["beneficiary"]["actor_type"],
        "payer_binding_sha256": _sha(quote["payer"]["endpoint"]),
        "beneficiary_binding_sha256": _sha(quote["beneficiary"]["endpoint"]),
        "amount_minor": quote["amount_minor"],
        "currency_from": quote["currency_from"],
        "receive_amount_minor": quote["receive_amount_minor"],
        "currency_to": quote["currency_to"],
    }


class BilateralAuthorityService:
    """Sandbox signing helper and trusted verifier for ETK-S -> ETK-R -> UTT.

    Production sender and receiver signing must occur outside RailOne under
    independently authenticated authorities. Issuance is for sandbox fixtures;
    signature ownership is enforced at every verification boundary.
    """

    AUTHORITY_VERSION = 4
    MAX_TTL_SECONDS = 900

    def __init__(self, signatures: SignatureService) -> None:
        self._signatures = signatures

    def _verify_beneficiary(self, evidence, quote, *, authorized_epoch, check_epoch):
        if not isinstance(evidence, SignatureEnvelope):
            raise PermissionError("BENEFICIARY_VERIFICATION_REQUIRED")
        beneficiary = quote["beneficiary"]
        endpoint = beneficiary["endpoint"]
        body = _verified(self._signatures, evidence, ArtifactType.BENEFICIARY_VERIFICATION,
                         endpoint["institution_id"])
        issued = evidence.protected["iat"]
        expiry = body.get("expires_at")
        expected = {
            "version": 1, "result": "IDENTITY_AND_ACCOUNT_MATCH",
            "quote_id": quote["quote_id"], "beneficiary_actor_id": beneficiary["actor_id"],
            "destination_sha256": _sha(endpoint), "currency": quote["currency_to"],
        }
        if (set(body) != set(expected) | {"expires_at", "verification_ref"}
                or type(body.get("version")) is not int
                or any(body.get(k) != v for k, v in expected.items())
                or endpoint["role"] != "CREDIT"
                or not isinstance(body.get("verification_ref"), str)
                or not 1 <= len(body["verification_ref"].strip()) <= 128):
            raise PermissionError("BENEFICIARY_VERIFICATION_MISMATCH")
        if (type(expiry) is not int or type(authorized_epoch) is not int
                or not issued <= authorized_epoch <= check_epoch < expiry
                or expiry > issued + self.MAX_TTL_SECONDS):
            raise PermissionError("BENEFICIARY_VERIFICATION_EXPIRED")

    def _bound_evidence(self, sender):
        try:
            return SignatureEnvelope.from_dict(sender["beneficiary_verification"])
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise PermissionError("BENEFICIARY_VERIFICATION_REQUIRED") from exc

    def issue_sender_authority(
        self, *, signed_quote: SignatureEnvelope, signing_key_id: str,
        authorized_at: datetime, expires_at: datetime,
        beneficiary_verification: SignatureEnvelope | None = None,
    ) -> SignatureEnvelope:
        epoch, expiry = _instant(authorized_at), _instant(expires_at)
        if not epoch < expiry <= epoch + self.MAX_TTL_SECONDS:
            raise ValueError("invalid sender authority window")
        result = self._signatures.verify_artifact(signed_quote, expected_artifact_type=ArtifactType.QUOTE)
        if not result.valid:
            raise PermissionError("QUOTE_INVALID:" + result.reason)
        quote = signed_quote.payload
        if quote["purpose"] != "PERSON_TO_PERSON":
            raise PermissionError("SENDER_FIRST_FLOW_P2P_ONLY")
        if not quote["issued_at"] <= epoch < quote["expires_at"]:
            raise PermissionError("QUOTE_NOT_ACTIVE")
        self._verify_beneficiary(beneficiary_verification, quote, authorized_epoch=epoch, check_epoch=epoch)
        core = {
            "beneficiary_verification": beneficiary_verification.to_dict(),
            "authority_version": self.AUTHORITY_VERSION,
            "authorization_scope": "INITIATE_SIGNED_QUOTE",
            **quote_commitment(quote),
            "authorized_at": epoch,
            "expires_at": expiry,
            "status": "ACTIVE",
            "custody_model": "NON_CUSTODIAL",
        }
        signed = self._signatures.sign_artifact(
            artifact_type=ArtifactType.ETK_S,
            payload={"etk_s_id": _id("ETKS", core), **core},
            key_id=signing_key_id, issued_at=authorized_at,
        )
        _verified(self._signatures, signed, ArtifactType.ETK_S, quote["payer"]["actor_id"])
        return signed

    def verify_sender(
        self, *, signed_quote: SignatureEnvelope,
        sender: SignatureEnvelope, at: datetime,
    ) -> None:
        epoch = _instant(at)
        result = self._signatures.verify_artifact(signed_quote, expected_artifact_type=ArtifactType.QUOTE)
        if not result.valid:
            raise PermissionError("QUOTE_INVALID:" + result.reason)
        quote = signed_quote.payload
        if quote["purpose"] != "PERSON_TO_PERSON":
            raise PermissionError("SENDER_FIRST_FLOW_P2P_ONLY")
        s = _verified(self._signatures, sender, ArtifactType.ETK_S, quote["payer"]["actor_id"])
        if any(s.get(k) != v for k, v in quote_commitment(quote).items()):
            raise PermissionError("SENDER_QUOTE_BINDING_MISMATCH")
        if (s.get("authority_version") != self.AUTHORITY_VERSION or
                s.get("authorization_scope") != "INITIATE_SIGNED_QUOTE" or
                s.get("status") != "ACTIVE" or
                s.get("custody_model") != "NON_CUSTODIAL" or
                s.get("etk_s_id") != _id("ETKS", {k: v for k, v in s.items() if k != "etk_s_id"})):
            raise PermissionError("SENDER_AUTHORITY_SCOPE_INVALID")
        issued, expiry = s.get("authorized_at"), s.get("expires_at")
        if not (type(issued) is int and type(expiry) is int and
                quote["issued_at"] <= issued < quote["expires_at"] and
                issued <= epoch < expiry and issued < expiry <= issued + self.MAX_TTL_SECONDS and
                sender.protected["iat"] == issued):
            raise PermissionError("SENDER_AUTHORITY_NOT_ACTIVE")
        self._verify_beneficiary(self._bound_evidence(s), quote, authorized_epoch=s.get("authorized_at"), check_epoch=epoch)

    def issue_receiver_acceptance(
        self, *, signed_quote: SignatureEnvelope, sender: SignatureEnvelope,
        signing_key_id: str, accepted_at: datetime, expires_at: datetime,
        mandate: SignatureEnvelope | None = None,
    ) -> SignatureEnvelope:
        self.verify_sender(signed_quote=signed_quote, sender=sender, at=accepted_at)
        epoch, expiry = _instant(accepted_at), _instant(expires_at)
        if not epoch < expiry <= epoch + self.MAX_TTL_SECONDS or expiry > sender.payload["expires_at"]:
            raise ValueError("invalid receiver authority window")
        quote = signed_quote.payload
        if not quote["issued_at"] <= epoch < quote["expires_at"]:
            raise PermissionError("QUOTE_NOT_ACTIVE")
        core = {
            "authority_version": self.AUTHORITY_VERSION,
            "authorization_scope": "ACCEPT_SENDER_INTENT",
            "receiver_confirmed": True,
            "participation_mode": "ACTIVE_ACCEPTANCE",
            **quote_commitment(quote),
            "etk_s_id": sender.payload["etk_s_id"],
            "etk_s_digest": sender.protected["payload_sha256"],
            "accepted_at": epoch,
            "expires_at": expiry,
            "status": "ACTIVE",
            "custody_model": "NON_CUSTODIAL",
        }
        if mandate is not None:
            core.update(participation_mode=MODE, receiver_confirmed=False, mandate=mandate.to_dict())
        owner = receiver_owner(self._signatures, core, quote,
                               sender_epoch=sender.payload["authorized_at"], check_epoch=epoch)
        signed = self._signatures.sign_artifact(
            artifact_type=ArtifactType.ETK_R,
            payload={"etk_r_id": _id("ETKR", core), **core},
            key_id=signing_key_id, issued_at=accepted_at,
        )
        _verified(self._signatures, signed, ArtifactType.ETK_R, owner)
        return signed

    def verify_receiver(
        self, *, signed_quote: SignatureEnvelope, sender: SignatureEnvelope,
        receiver: SignatureEnvelope, at: datetime,
    ) -> None:
        self.verify_sender(signed_quote=signed_quote, sender=sender, at=at)
        epoch = _instant(at)
        quote = signed_quote.payload
        r = _verified(self._signatures, receiver, ArtifactType.ETK_R,
                      receiver_owner(self._signatures, receiver.payload, quote,
                                     sender_epoch=sender.payload["authorized_at"], check_epoch=epoch))
        if any(r.get(k) != v for k, v in quote_commitment(quote).items()):
            raise PermissionError("RECEIVER_QUOTE_BINDING_MISMATCH")
        if (r.get("authority_version") != self.AUTHORITY_VERSION or
                r.get("authorization_scope") != "ACCEPT_SENDER_INTENT" or
                r.get("status") != "ACTIVE" or
                r.get("custody_model") != "NON_CUSTODIAL" or
                r.get("etk_s_id") != sender.payload["etk_s_id"] or
                r.get("etk_s_digest") != sender.protected["payload_sha256"] or
                r.get("etk_r_id") != _id("ETKR", {k: v for k, v in r.items() if k != "etk_r_id"})):
            raise PermissionError("BILATERAL_CHAIN_BROKEN")
        issued, expiry = r.get("accepted_at"), r.get("expires_at")
        if not (type(issued) is int and type(expiry) is int and
                sender.payload["authorized_at"] < issued <= epoch < expiry <= sender.payload["expires_at"] and
                quote["issued_at"] <= issued < quote["expires_at"] and
                issued < expiry <= issued + self.MAX_TTL_SECONDS and
                receiver.protected["iat"] == issued):
            raise PermissionError("BILATERAL_AUTHORITY_EXPIRED_OR_REORDERED")

    def verify_utt(
        self, *, signed_utt: SignatureEnvelope, sender: SignatureEnvelope,
        receiver: SignatureEnvelope, at: datetime,
    ) -> None:
        epoch = _instant(at)
        verification = self._signatures.verify_artifact(signed_utt, expected_artifact_type=ArtifactType.UTT)
        if not verification.valid:
            raise PermissionError("UTT_INVALID:" + verification.reason)
        utt = signed_utt.payload
        if utt.get("authority_version") != self.AUTHORITY_VERSION or utt["origin"].get("context_type") != "P2P":
            raise PermissionError("BILATERAL_UTT_REQUIRED")
        s = _verified(self._signatures, sender, ArtifactType.ETK_S, utt["payer"]["actor_id"])
        r = _verified(self._signatures, receiver, ArtifactType.ETK_R,
                      receiver_owner(self._signatures, receiver.payload, utt,
                                     sender_epoch=s["authorized_at"], check_epoch=utt["accepted_at"]))
        self._verify_beneficiary(self._bound_evidence(s), utt, authorized_epoch=s.get("authorized_at"),
                                 check_epoch=utt["accepted_at"])
        expected = quote_commitment(utt)
        if any(s.get(k) != v or r.get(k) != v for k, v in expected.items()):
            raise PermissionError("BILATERAL_QUOTE_BINDING_MISMATCH")
        if (s.get("authority_version") != self.AUTHORITY_VERSION or
                r.get("authority_version") != self.AUTHORITY_VERSION or
                s.get("authorization_scope") != "INITIATE_SIGNED_QUOTE" or
                r.get("authorization_scope") != "ACCEPT_SENDER_INTENT" or
                s.get("status") != "ACTIVE" or r.get("status") != "ACTIVE" or
                s.get("custody_model") != "NON_CUSTODIAL" or r.get("custody_model") != "NON_CUSTODIAL" or
                r.get("etk_s_id") != s.get("etk_s_id") or
                r.get("etk_s_digest") != sender.protected["payload_sha256"] or
                utt.get("etk_s_id") != s.get("etk_s_id") or
                utt.get("etk_r_id") != r.get("etk_r_id") or
                utt.get("etk_s_digest") != sender.protected["payload_sha256"] or
                utt.get("etk_r_digest") != receiver.protected["payload_sha256"]):
            raise PermissionError("BILATERAL_CHAIN_BROKEN")
        if not (type(s.get("authorized_at")) is int and type(r.get("accepted_at")) is int and
                type(s.get("expires_at")) is int and type(r.get("expires_at")) is int and
                s["authorized_at"] < r["accepted_at"] <= utt["accepted_at"] <= epoch < r["expires_at"] <= s["expires_at"] and
                s["authorized_at"] < s["expires_at"] <= s["authorized_at"] + self.MAX_TTL_SECONDS and
                r["accepted_at"] < r["expires_at"] <= r["accepted_at"] + self.MAX_TTL_SECONDS and
                sender.protected["iat"] == s["authorized_at"] and
                receiver.protected["iat"] == r["accepted_at"]):
            raise PermissionError("BILATERAL_AUTHORITY_EXPIRED_OR_REORDERED")
        if (s["etk_s_id"] != _id("ETKS", {k: v for k, v in s.items() if k != "etk_s_id"}) or
                r["etk_r_id"] != _id("ETKR", {k: v for k, v in r.items() if k != "etk_r_id"})):
            raise PermissionError("BILATERAL_AUTHORITY_ID_MISMATCH")
