"""Authenticated, non-signing P2P bilateral HTTP application operations.

The API NEVER signs ETK-S or ETK-R for a human principal. All authorities are
produced by independent signers; authenticated actor scope plus signed ownership
must agree. Pre-UTT checks are stateless; the existing acceptance store atomically
persists the bilateral lock with the UTT.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from railone_authority.bilateral import BilateralAuthorityService
from railone_contracts import (
    ContextType, OriginContext, PaymentPurpose, QuoteAcceptanceCommand,
    QuoteAcceptanceService,
)
from railone_crypto.canonical_json import canonical_json_bytes
from railone_crypto.signature_service import SignatureEnvelope

from .auth import AuthenticatedPrincipal, PrincipalType


_MAX_REQUEST_BYTES = 32768
_IDEMPOTENCY_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:\-]{7,127}\Z")


class BilateralP2PApi:
    """Inject into RailOneApiFacade; all endpoints remain unavailable by default.

    A HUMAN principal with a trusted continuity_uid claim represents the payer
    or beneficiary. Delegated institutional signing is deliberately out of scope
    until an explicit scoped delegation model is certified.
    """

    def __init__(
        self, *, bilateral: BilateralAuthorityService,
        acceptance: QuoteAcceptanceService,
        origin_system: str = "RAILONE_CLIENT",
    ) -> None:
        if not acceptance.bilateral_p2p_required:
            raise ValueError("authenticated bilateral API requires strict P2P acceptance")
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{1,47}", origin_system):
            raise ValueError("origin_system must be an approved uppercase identifier")
        self._bilateral = bilateral
        self._acceptance = acceptance
        self._origin_system = origin_system

    def verify_sender(
        self, *, principal: AuthenticatedPrincipal,
        request: Mapping[str, Any], at: datetime,
    ) -> dict[str, Any]:
        _bounded(request)
        quote = _envelope(request, "signed_quote")
        sender = _envelope(request, "sender_authority")
        _principal_owns(principal, quote, "payer")
        _verify(lambda: self._bilateral.verify_sender(signed_quote=quote, sender=sender, at=at))
        return {
            "status": "ETK_S_VERIFIED", "quote_id": quote.payload["quote_id"],
            "etk_s_id": sender.payload["etk_s_id"],
            "etk_s_digest": sender.protected["payload_sha256"],
            "expires_at": sender.payload["expires_at"],
            "persisted": False,
        }

    def verify_receiver(
        self, *, principal: AuthenticatedPrincipal,
        request: Mapping[str, Any], at: datetime,
    ) -> dict[str, Any]:
        _bounded(request)
        quote = _envelope(request, "signed_quote")
        sender = _envelope(request, "sender_authority")
        receiver = _envelope(request, "receiver_authority")
        _principal_owns(principal, quote, "beneficiary")
        _verify(lambda: self._bilateral.verify_receiver(
            signed_quote=quote, sender=sender, receiver=receiver, at=at,
        ))
        return {
            "status": "ETK_R_VERIFIED", "quote_id": quote.payload["quote_id"],
            "etk_s_id": sender.payload["etk_s_id"],
            "etk_r_id": receiver.payload["etk_r_id"],
            "etk_r_digest": receiver.protected["payload_sha256"],
            "expires_at": receiver.payload["expires_at"],
            "persisted": False,
        }

    def create_utt(
        self, *, principal: AuthenticatedPrincipal,
        request: Mapping[str, Any], idempotency_key: str, at: datetime,
    ) -> dict[str, Any]:
        _bounded(request)
        if not isinstance(idempotency_key, str) or not _IDEMPOTENCY_KEY.fullmatch(idempotency_key):
            raise PermissionError("INVALID_IDEMPOTENCY_KEY")
        quote = _envelope(request, "signed_quote")
        sender = _envelope(request, "sender_authority")
        receiver = _envelope(request, "receiver_authority")
        _principal_owns(principal, quote, "payer")
        _verify(lambda: self._bilateral.verify_receiver(
            signed_quote=quote, sender=sender, receiver=receiver, at=at,
        ))
        origin_intent_id = request.get("origin_intent_id")
        if (not isinstance(origin_intent_id, str) or
                not 1 <= len(origin_intent_id) <= 128 or not origin_intent_id.strip()):
            raise PermissionError("INVALID_ORIGIN_INTENT_ID")
        origin = OriginContext(
            origin_system=self._origin_system, origin_intent_id=origin_intent_id,
            context_type=ContextType.P2P, purpose=PaymentPurpose.PERSON_TO_PERSON,
            continuity_uid=principal.scopes.continuity_uid,
        )
        command = QuoteAcceptanceCommand(
            signed_quote=quote, sender_authority=sender, receiver_authority=receiver,
            origin=origin, authorization_method="SIGNED_BILATERAL_ETK_V3",
            authorization_reference=receiver.payload["etk_r_id"],
            idempotency_key=idempotency_key,
        )
        accepted = self._acceptance.accept(command, at=at)
        return {
            "status": "ACCEPTED", "authority_version": 4,
            "quote_id": accepted.contract.quote_id,
            "utt_id": accepted.contract.utt_id,
            "replayed": accepted.replayed,
        }


def _bounded(request: Mapping[str, Any]) -> None:
    if not isinstance(request, Mapping):
        raise PermissionError("INVALID_BILATERAL_REQUEST")
    try:
        size = len(canonical_json_bytes(request))
    except (ValueError, TypeError, OverflowError) as exc:
        raise PermissionError("INVALID_BILATERAL_REQUEST") from None
    if size > _MAX_REQUEST_BYTES:
        raise PermissionError("BILATERAL_REQUEST_TOO_LARGE")


def _envelope(request: Mapping[str, Any], field: str) -> SignatureEnvelope:
    value = request.get(field)
    if not isinstance(value, Mapping):
        raise PermissionError("INVALID_SIGNED_ENVELOPE")
    try:
        return SignatureEnvelope.from_dict(value)
    except (ValueError, TypeError, KeyError):
        raise PermissionError("INVALID_SIGNED_ENVELOPE") from None


def _principal_owns(
    principal: AuthenticatedPrincipal, quote: SignatureEnvelope, role: str,
) -> None:
    if principal.principal_type is not PrincipalType.HUMAN:
        raise PermissionError("BILATERAL_HUMAN_PRINCIPAL_REQUIRED")
    uid = principal.scopes.continuity_uid
    if uid is None:
        raise PermissionError("BILATERAL_CONTINUITY_SCOPE_REQUIRED")
    try:
        actor = quote.payload[role]
        owner = actor["actor_id"]
        if not isinstance(owner, str):
            raise PermissionError("INVALID_BILATERAL_ACTOR")
    except (KeyError, TypeError):
        raise PermissionError("INVALID_BILATERAL_ACTOR") from None
    if owner != uid:
        raise PermissionError("BILATERAL_ACTOR_SCOPE_MISMATCH")


def _verify(check) -> None:
    """Normalize malformed signed artifacts; never publish parsing details."""
    try:
        check()
    except (ValueError, TypeError, KeyError, AttributeError):
        raise PermissionError("INVALID_BILATERAL_ARTIFACT") from None
