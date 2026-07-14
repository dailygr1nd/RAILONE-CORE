"""Exactly-once quote acceptance and immutable UTT creation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from railone_authority.service import ExecutionAuthorityService
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


@dataclass(frozen=True, slots=True)
class QuoteAcceptanceResult:
    contract: AcceptedContract
    replayed: bool


class QuoteAcceptanceService:
    def __init__(
        self,
        *,
        signatures: SignatureService,
        authority: ExecutionAuthorityService,
        store: ContractStore,
        utt_signing_key_id: str,
        authority_signing_key_id: str,
    ) -> None:
        self._signatures = signatures
        self._authority = authority
        self._store = store
        self._utt_signing_key_id = utt_signing_key_id
        self._authority_signing_key_id = authority_signing_key_id

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
        request_sha256 = hashlib.sha256(
            canonical_json_bytes(request_material)
        ).hexdigest()

        existing = self._store.resolve_idempotency(
            idempotency_key, request_sha256
        )
        if existing is not None:
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
        utt_hash = hashlib.sha256(
            canonical_json_bytes(commercial_core)
        ).hexdigest().upper()
        utt_id = f"UTT-{utt_hash[:32]}"

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
        contract = AcceptedContract(
            signed_utt=signed_utt,
            sender_authority=sender_authority,
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
