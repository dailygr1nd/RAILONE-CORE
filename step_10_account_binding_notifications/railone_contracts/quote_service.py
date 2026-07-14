"""Signed, expiring RailOne commercial quote issuance."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from railone_crypto.canonical_json import canonical_json_bytes
from railone_crypto.signature_service import ArtifactType, SignatureEnvelope, SignatureService

from .models import AccountRole, QuoteTerms
from railone_partners import EndpointValidator


class QuoteService:
    MAX_QUOTE_TTL_SECONDS = 5 * 60

    def __init__(
        self,
        signatures: SignatureService,
        *,
        endpoints: EndpointValidator | None = None,
        allow_unverified_endpoints_for_tests: bool = False,
    ) -> None:
        self._signatures = signatures
        self._endpoints = endpoints
        self._allow_unverified = allow_unverified_endpoints_for_tests

    def issue_quote(
        self,
        *,
        terms: QuoteTerms,
        signing_key_id: str,
        issued_at: datetime,
        expires_at: datetime,
    ) -> SignatureEnvelope:
        if issued_at.tzinfo is None or expires_at.tzinfo is None:
            raise ValueError("quote timestamps must be timezone-aware")
        issued = issued_at.astimezone(timezone.utc)
        expiry = expires_at.astimezone(timezone.utc)
        ttl = (expiry - issued).total_seconds()
        if ttl <= 0:
            raise ValueError("quote expiry must be after issuance")
        if ttl > self.MAX_QUOTE_TTL_SECONDS:
            raise ValueError("quote TTL exceeds pilot maximum")

        terms_payload = terms.to_payload()
        if self._endpoints is None:
            if not self._allow_unverified:
                raise RuntimeError("partner endpoint validator is required")
        else:
            self._endpoints.validate_endpoint(
                actor_id=terms.payer.actor_id, endpoint=terms.payer.endpoint,
                required_role=AccountRole.DEBIT, currency=terms.currency_from,
            )
            self._endpoints.validate_endpoint(
                actor_id=terms.beneficiary.actor_id,
                endpoint=terms.beneficiary.endpoint,
                required_role=AccountRole.CREDIT, currency=terms.currency_to,
            )
        core = {
            **terms_payload,
            "issued_at": int(issued.timestamp()),
            "expires_at": int(expiry.timestamp()),
        }
        quote_hash = hashlib.sha256(canonical_json_bytes(core)).hexdigest().upper()
        payload = {"quote_id": f"Q-{quote_hash[:32]}", **core}
        return self._signatures.sign_artifact(
            artifact_type=ArtifactType.QUOTE,
            payload=payload,
            key_id=signing_key_id,
            issued_at=issued,
        )
