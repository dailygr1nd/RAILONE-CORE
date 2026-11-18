"""Atomic quote-acceptance persistence contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from typing import Protocol

from railone_crypto.signature_service import SignatureEnvelope


class IdempotencyConflictError(RuntimeError):
    pass


class QuoteAlreadyAcceptedError(RuntimeError):
    pass


class UttNotFoundError(LookupError):
    pass


@dataclass(frozen=True, slots=True)
class AcceptedContract:
    signed_utt: SignatureEnvelope
    sender_authority: SignatureEnvelope
    quote_id: str
    utt_id: str
    request_sha256: str
    accepted_at: datetime
    receiver_authority: SignatureEnvelope | None = None


class ContractStore(Protocol):
    def resolve_idempotency(
        self, idempotency_key: str, request_sha256: str
    ) -> AcceptedContract | None:
        ...

    def commit_acceptance(
        self,
        *,
        idempotency_key: str,
        contract: AcceptedContract,
    ) -> tuple[AcceptedContract, bool]:
        """Persist quote, UTT, ETK-S, and idempotency atomically.

        The boolean is true when a concurrent identical request already won.
        """
        ...

    def require_utt(self, utt_id: str) -> SignatureEnvelope:
        ...

    def require_bilateral_authorities(self, utt_id: str) -> tuple[SignatureEnvelope, SignatureEnvelope]:
        ...


class InMemoryContractStore:
    """Test-only model of required database uniqueness and transaction rules."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._idempotency: dict[str, AcceptedContract] = {}
        self._quote_to_utt: dict[str, str] = {}
        self._utts: dict[str, SignatureEnvelope] = {}
        self._contracts: dict[str, AcceptedContract] = {}

    def resolve_idempotency(
        self, idempotency_key: str, request_sha256: str
    ) -> AcceptedContract | None:
        with self._lock:
            existing = self._idempotency.get(idempotency_key)
            if existing is None:
                return None
            if existing.request_sha256 != request_sha256:
                raise IdempotencyConflictError(
                    "idempotency key was already used for different request material"
                )
            return existing

    def commit_acceptance(
        self,
        *,
        idempotency_key: str,
        contract: AcceptedContract,
    ) -> tuple[AcceptedContract, bool]:
        with self._lock:
            existing = self._idempotency.get(idempotency_key)
            if existing is not None:
                if existing.request_sha256 != contract.request_sha256:
                    raise IdempotencyConflictError(
                        "idempotency key was already used for different request material"
                    )
                return existing, True

            prior_utt = self._quote_to_utt.get(contract.quote_id)
            if prior_utt is not None:
                raise QuoteAlreadyAcceptedError(
                    f"quote already accepted as {prior_utt}"
                )
            if contract.utt_id in self._utts:
                raise RuntimeError("UTT identifier collision")

            if (contract.receiver_authority is not None and
                    contract.receiver_authority.payload.get("participation_mode") == "BENEFICIARY_PREAUTHORIZED"):
                raise PermissionError("DELEGATED_ACCEPTANCE_REQUIRES_DURABLE_MANDATE")
            self._utts[contract.utt_id] = contract.signed_utt
            self._contracts[contract.utt_id] = contract
            self._quote_to_utt[contract.quote_id] = contract.utt_id
            self._idempotency[idempotency_key] = contract
            return contract, False

    def require_utt(self, utt_id: str) -> SignatureEnvelope:
        with self._lock:
            utt = self._utts.get(utt_id)
            if utt is None:
                raise UttNotFoundError(f"persisted UTT not found: {utt_id}")
            return utt

    def require_bilateral_authorities(self, utt_id: str) -> tuple[SignatureEnvelope, SignatureEnvelope]:
        with self._lock:
            contract = self._contracts.get(utt_id)
            if contract is None or contract.receiver_authority is None:
                raise PermissionError("PERSISTED_BILATERAL_AUTHORITIES_MISSING")
            return contract.sender_authority, contract.receiver_authority
