"""Exactly-once quote acceptance and immutable UTT creation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import wraps
from datetime import datetime, timedelta, timezone

from railone_authority.service import ExecutionAuthorityService
from railone_authority.bilateral import BilateralAuthorityService
from railone_security.incident_audit import SecurityAuditWriter
from railone_crypto.canonical_json import canonical_json_bytes
from railone_crypto.signature_service import ArtifactType, SignatureEnvelope, SignatureService

from .models import ContextType, OriginContext, require_text
from .store import AcceptedContract, ContractStore


@dataclass(frozen=True, slots=True)
class QuoteAcceptanceCommand:
    signed_quote: SignatureEnvelope
    origin: OriginContext
    authorization_method: str
    authorization_reference: str
    idempotency_key: str
    authority_ttl_seconds: int = 10 * 60
    receiver_authority: SignatureEnvelope | None = None
    sender_authority: SignatureEnvelope | None = None


@dataclass(frozen=True, slots=True)
class QuoteAcceptanceResult:
    contract: AcceptedContract
    replayed: bool


def _audit_acceptance_denial(fn):
    @wraps(fn)
    def wrapped(self, command, *, at=None):
        try:
            return fn(self, command, at=at)
        except (PermissionError, ValueError) as exc:
            if (self._security_audit is not None and
                    command.origin.context_type is ContextType.P2P):
                self._security_audit.record_rejection(
                    event_type="BILATERAL_AUTH_REJECTED", operation="ACCEPT",
                    correlation_ref=str(command.signed_quote.payload.get("quote_id", "INVALID-QUOTE")),
                    error=exc, at=at or datetime.now(timezone.utc),
                )
            raise
    return wrapped


class QuoteAcceptanceService:
    def __init__(
        self,
        *,
        signatures: SignatureService,
        authority: ExecutionAuthorityService,
        store: ContractStore,
        utt_signing_key_id: str,
        authority_signing_key_id: str,
        require_bilateral_p2p: bool = False,
        security_audit: SecurityAuditWriter | None = None,
    ) -> None:
        self._signatures = signatures
        self._authority = authority
        self._store = store
        self._utt_signing_key_id = utt_signing_key_id
        self._authority_signing_key_id = authority_signing_key_id
        self._bilateral = BilateralAuthorityService(signatures)
        self._require_bilateral_p2p = require_bilateral_p2p
        self._security_audit = security_audit

    @property
    def bilateral_p2p_required(self) -> bool:
        return self._require_bilateral_p2p

    @_audit_acceptance_denial
    def accept(
        self,
        command: QuoteAcceptanceCommand,
        *,
        at: datetime | None = None,
    ) -> QuoteAcceptanceResult:
        idempotency_key = require_text("idempotency_key", command.idempotency_key)
        origin_payload = command.origin.to_payload()
        request_material = {
            "signed_quote": command.signed_quote.to_dict(),
            "origin": origin_payload,
            "authorization_method": require_text(
                "authorization_method", command.authorization_method
            ),
            "authorization_reference": require_text(
                "authorization_reference", command.authorization_reference
            ),
            "authority_ttl_seconds": command.authority_ttl_seconds,
        }
        # Preserve the existing v0.16 idempotency fingerprint for legacy callers.
        # Only v3 requests include the two pre-signed authorization artifacts.
        if command.receiver_authority is not None or command.sender_authority is not None:
            request_material["receiver_authority"] = (
                command.receiver_authority.to_dict() if command.receiver_authority else None
            )
            request_material["sender_authority"] = (
                command.sender_authority.to_dict() if command.sender_authority else None
            )
        request_sha256 = hashlib.sha256(
            canonical_json_bytes(request_material)
        ).hexdigest()

        existing = self._store.resolve_idempotency(
            idempotency_key, request_sha256
        )
        if existing is not None:
            # Strict mode must not return a pre-v3 P2P UTT simply because an
            # idempotency key matches an older acceptance record.
            if (self._require_bilateral_p2p and
                    command.origin.context_type is ContextType.P2P and
                    (existing.signed_utt.payload.get("authority_version") != 4 or
                     existing.receiver_authority is None)):
                raise PermissionError("SENDER_FIRST_BILATERAL_V4_REQUIRED")
            return QuoteAcceptanceResult(existing, replayed=True)

        if at is not None and at.tzinfo is None:
            raise ValueError("acceptance timestamp must be timezone-aware")
        accepted_at = (at or datetime.now(timezone.utc)).astimezone(timezone.utc)
        quote_result = self._signatures.verify_artifact(
            command.signed_quote,
            expected_artifact_type=ArtifactType.QUOTE,
        )
        if not quote_result.valid:
            raise PermissionError(f"quote rejected: {quote_result.reason}")

        quote = command.signed_quote.payload
        accepted_epoch = int(accepted_at.timestamp())
        if accepted_epoch < quote["issued_at"]:
            raise PermissionError("quote rejected: QUOTE_NOT_YET_VALID")
        if accepted_epoch >= quote["expires_at"]:
            raise PermissionError("quote rejected: QUOTE_EXPIRED")
        if quote["purpose"] != origin_payload["purpose"]:
            raise PermissionError("quote purpose does not match origin purpose")
        if command.origin.context_type is ContextType.MERCHANT:
            if quote["payer"]["actor_id"] != origin_payload["merchant_id"]:
                raise PermissionError("quote payer does not match merchant context")
        if command.origin.context_type is ContextType.P2P:
            if quote["payer"]["actor_id"] != origin_payload["continuity_uid"]:
                raise PermissionError("quote payer does not match P2P continuity")

        ttl = command.authority_ttl_seconds
        if isinstance(ttl, bool) or not isinstance(ttl, int):
            raise TypeError("authority_ttl_seconds must be an integer")
        if not 1 <= ttl <= ExecutionAuthorityService.MAX_AUTHORITY_SECONDS:
            raise ValueError("authority TTL is outside the permitted range")

        quote_payload_sha256 = hashlib.sha256(
            canonical_json_bytes(quote)
        ).hexdigest()
        commercial_core = {
            "quote_id": quote["quote_id"],
            "quote_payload_sha256": quote_payload_sha256,
            "payer": quote["payer"],
            "beneficiary": quote["beneficiary"],
            "purpose": quote["purpose"],
            "amount_minor": quote["amount_minor"],
            "currency_from": quote["currency_from"],
            "receive_amount_minor": quote["receive_amount_minor"],
            "currency_to": quote["currency_to"],
            "total_fee_minor": quote["total_fee_minor"],
            "routing_budget_minor": quote["routing_budget_minor"],
            "fx_rate": quote["fx_rate"],
            "corridor_id": quote["corridor_id"],
            "service_level": quote["service_level"],
            "routing_policy_id": quote["routing_policy_id"],
            "pricing_version": quote["pricing_version"],
            "pricing_model": "PER_INTENT",
            "max_attempts": quote["max_attempts"],
            "origin": origin_payload,
            "accepted_at": accepted_epoch,
            "acceptance_request_sha256": request_sha256,
            "custody_model": "NON_CUSTODIAL",
            "endpoint_model_version": quote["endpoint_model_version"],
        }
        bilateral = command.receiver_authority is not None or command.sender_authority is not None
        if command.origin.context_type is ContextType.P2P and self._require_bilateral_p2p and not bilateral:
            raise PermissionError("BILATERAL_RECEIVER_ACCEPTANCE_REQUIRED")
        if bilateral:
            if (command.origin.context_type is not ContextType.P2P
                    or command.receiver_authority is None or command.sender_authority is None):
                raise PermissionError("BILATERAL_P2P_AUTHORITIES_REQUIRED")
            self._bilateral.verify_sender(
                signed_quote=command.signed_quote, sender=command.sender_authority,
                at=accepted_at,
            )
            receiver = command.receiver_authority
            self._bilateral.verify_receiver(
                signed_quote=command.signed_quote, sender=command.sender_authority,
                receiver=receiver, at=accepted_at,
            )
            # ETK-S is independently signed by the payer; RailOne never
            # signs a user's authorization just because an API caller named a key.
            sender_authority = command.sender_authority
            commercial_core.update({
                "authority_version": 4,
                "etk_s_id": sender_authority.payload["etk_s_id"],
                "etk_r_id": receiver.payload["etk_r_id"],
                "etk_s_digest": sender_authority.protected["payload_sha256"],
                "etk_r_digest": receiver.protected["payload_sha256"],
            })
        else:
            receiver = None

        utt_hash = hashlib.sha256(
            canonical_json_bytes(commercial_core)
        ).hexdigest().upper()
        utt_id = f"UTT-{utt_hash[:32]}"

        if not bilateral:
            sender_authority = self._authority.issue_sender_authority(
                utt_id=utt_id,
                quote_id=quote["quote_id"],
                sender_actor_type=quote["payer"]["actor_type"],
                sender_reference=quote["payer"]["actor_id"],
                amount_minor=quote["amount_minor"],
                currency=quote["currency_from"],
                origin_context=origin_payload,
                authorization_method=command.authorization_method,
                authorization_reference=command.authorization_reference,
                signing_key_id=self._authority_signing_key_id,
                authorized_at=accepted_at,
                expires_at=accepted_at + timedelta(seconds=ttl),
            )
        utt_payload = {
            "utt_id": utt_id,
            **commercial_core,
            "etk_s_id": sender_authority.payload["etk_s_id"],
            "commercial_state": "ACCEPTED",
        }
        signed_utt = self._signatures.sign_artifact(
            artifact_type=ArtifactType.UTT,
            payload=utt_payload,
            key_id=self._utt_signing_key_id,
            issued_at=accepted_at,
        )
        if bilateral:
            self._bilateral.verify_utt(
                signed_utt=signed_utt, sender=sender_authority,
                receiver=receiver, at=accepted_at,
            )
        contract = AcceptedContract(
            signed_utt=signed_utt,
            sender_authority=sender_authority,
            receiver_authority=receiver,
            quote_id=quote["quote_id"],
            utt_id=utt_id,
            request_sha256=request_sha256,
            accepted_at=accepted_at,
        )
        stored, raced = self._store.commit_acceptance(
            idempotency_key=idempotency_key,
            contract=contract,
        )
        return QuoteAcceptanceResult(stored, replayed=raced)
