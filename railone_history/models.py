"""Privacy-limited transaction-history projection models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum


class SubjectKind(StrEnum):
    CONTINUITY_UID = "CONTINUITY_UID"
    MERCHANT_ID = "MERCHANT_ID"
    BRANCH_ID = "BRANCH_ID"
    PARTNER_ID = "PARTNER_ID"


class TransactionRole(StrEnum):
    PAYER = "PAYER"
    BENEFICIARY = "BENEFICIARY"
    AUTHORIZER = "AUTHORIZER"
    ORIGIN_MERCHANT = "ORIGIN_MERCHANT"
    ORIGIN_BRANCH = "ORIGIN_BRANCH"
    ORIGIN_PARTNER = "ORIGIN_PARTNER"


class AccessOutcome(StrEnum):
    ALLOWED = "ALLOWED"
    DENIED = "DENIED"


READ_ANY_PERMISSION = "railone.transactions.read:any"


@dataclass(frozen=True, slots=True)
class UttTransactionProjection:
    utt_id: str
    utt_payload_sha256: str
    quote_id: str
    purpose: str
    context_type: str
    amount_minor: int
    currency_from: str
    receive_amount_minor: int
    currency_to: str
    commercial_state: str
    accepted_at: datetime
    indexed_at: datetime


@dataclass(frozen=True, slots=True)
class TransactionSubjectLink:
    utt_id: str
    subject_kind: SubjectKind
    subject_id: str
    roles: tuple[TransactionRole, ...]
    linked_at: datetime


@dataclass(frozen=True, slots=True)
class TransactionReadContext:
    principal_id: str
    continuity_uid: str | None = None
    merchant_ids: tuple[str, ...] = ()
    branch_ids: tuple[str, ...] = ()
    partner_ids: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    access_reason: str | None = None


@dataclass(frozen=True, slots=True)
class TransactionHistoryEntry:
    transaction: UttTransactionProjection
    matched_roles: tuple[TransactionRole, ...]


@dataclass(frozen=True, slots=True)
class TransactionHistoryPage:
    entries: tuple[TransactionHistoryEntry, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class TransactionAccessAudit:
    audit_id: str
    principal_id: str
    target_kind: str
    target_id: str
    outcome: AccessOutcome
    access_reason: str
    occurred_at: datetime


def utc_datetime_from_epoch(value: int) -> datetime:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("epoch timestamp must be an integer")
    return datetime.fromtimestamp(value, tz=timezone.utc)
