"""UTT indexing and permissioned transaction-history queries."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from collections.abc import Mapping
from uuid import uuid4

from railone_contracts.models import require_text
from railone_contracts.store import ContractStore
from railone_crypto.signature_service import ArtifactType, SignatureService
from railone_identity.continuity import IdentityRepository

from .models import (
    AccessOutcome,
    READ_ANY_PERMISSION,
    SubjectKind,
    TransactionAccessAudit,
    TransactionHistoryEntry,
    TransactionHistoryPage,
    TransactionReadContext,
    TransactionRole,
    TransactionSubjectLink,
    UttTransactionProjection,
    utc_datetime_from_epoch,
)
from .store import TransactionHistoryStore


class TransactionAccessDeniedError(PermissionError):
    pass


def _instant(at: datetime | None) -> datetime:
    value = at or datetime.now(timezone.utc)
    if value.tzinfo is None:
        raise ValueError("transaction-history timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


class UttTransactionIndexer:
    def __init__(
        self,
        *,
        signatures: SignatureService,
        contracts: ContractStore,
        identities: IdentityRepository,
        history: TransactionHistoryStore,
    ) -> None:
        self._signatures = signatures
        self._contracts = contracts
        self._identities = identities
        self._history = history

    def index(self, *, utt_id: str, at: datetime | None = None) -> UttTransactionProjection:
        indexed_at = _instant(at)
        signed_utt = self._contracts.require_utt(require_text("utt_id", utt_id))
        verification = self._signatures.verify_artifact(
            signed_utt, expected_artifact_type=ArtifactType.UTT
        )
        if not verification.valid:
            raise PermissionError(f"UTT rejected: {verification.reason}")
        utt = signed_utt.payload
        origin = utt["origin"]
        projection = UttTransactionProjection(
            utt_id=utt_id,
            utt_payload_sha256=signed_utt.protected["payload_sha256"],
            quote_id=utt["quote_id"],
            purpose=utt["purpose"],
            context_type=origin["context_type"],
            amount_minor=utt["amount_minor"],
            currency_from=utt["currency_from"],
            receive_amount_minor=utt["receive_amount_minor"],
            currency_to=utt["currency_to"],
            commercial_state=utt["commercial_state"],
            accepted_at=utc_datetime_from_epoch(utt["accepted_at"]),
            indexed_at=indexed_at,
        )
        roles_by_subject: dict[tuple[SubjectKind, str], set[TransactionRole]] = {}

        def add(kind: SubjectKind, subject_id: str, role: TransactionRole) -> None:
            normalized = require_text("subject_id", subject_id).upper()
            roles_by_subject.setdefault((kind, normalized), set()).add(role)

        continuity_uid = origin.get("continuity_uid")
        if continuity_uid is not None:
            self._require_identity(continuity_uid)
            role = (
                TransactionRole.PAYER
                if origin["context_type"] == "P2P"
                else TransactionRole.AUTHORIZER
            )
            add(SubjectKind.CONTINUITY_UID, continuity_uid, role)
        if origin.get("merchant_id") is not None:
            add(
                SubjectKind.MERCHANT_ID,
                origin["merchant_id"],
                TransactionRole.ORIGIN_MERCHANT,
            )
        if origin.get("branch_id") is not None:
            add(
                SubjectKind.BRANCH_ID,
                origin["branch_id"],
                TransactionRole.ORIGIN_BRANCH,
            )
        if origin.get("partner_id") is not None:
            add(
                SubjectKind.PARTNER_ID,
                origin["partner_id"],
                TransactionRole.ORIGIN_PARTNER,
            )

        self._add_actor(roles_by_subject, utt["payer"], TransactionRole.PAYER)
        self._add_actor(
            roles_by_subject, utt["beneficiary"], TransactionRole.BENEFICIARY
        )
        links = tuple(
            TransactionSubjectLink(
                utt_id=utt_id,
                subject_kind=kind,
                subject_id=subject_id,
                roles=tuple(sorted(roles, key=lambda role: role.value)),
                linked_at=indexed_at,
            )
            for (kind, subject_id), roles in sorted(
                roles_by_subject.items(), key=lambda item: (item[0][0].value, item[0][1])
            )
        )
        return self._history.commit(projection, links)

    def _add_actor(
        self,
        roles_by_subject: dict[tuple[SubjectKind, str], set[TransactionRole]],
        actor: Mapping[str, object],
        role: TransactionRole,
    ) -> None:
        actor_type = str(actor["actor_type"]).upper()
        actor_id = str(actor["actor_id"]).upper()
        if actor_id.startswith("CUID-"):
            self._require_identity(actor_id)
            roles_by_subject.setdefault(
                (SubjectKind.CONTINUITY_UID, actor_id), set()
            ).add(role)
        elif actor_type == "MERCHANT":
            roles_by_subject.setdefault((SubjectKind.MERCHANT_ID, actor_id), set()).add(role)
        elif actor_type == "BRANCH":
            roles_by_subject.setdefault((SubjectKind.BRANCH_ID, actor_id), set()).add(role)
        elif actor_type == "PARTNER":
            roles_by_subject.setdefault((SubjectKind.PARTNER_ID, actor_id), set()).add(role)

    def _require_identity(self, continuity_uid: str) -> None:
        normalized = require_text("continuity_uid", continuity_uid).upper()
        if self._identities.get_by_continuity_uid(normalized) is None:
            raise PermissionError(f"unknown continuity UID cannot be indexed: {normalized}")


class TransactionHistoryService:
    def __init__(self, history: TransactionHistoryStore) -> None:
        self._history = history

    def get_by_utt(
        self,
        *,
        utt_id: str,
        access: TransactionReadContext,
        at: datetime | None = None,
    ) -> TransactionHistoryEntry:
        instant = _instant(at)
        normalized_utt = require_text("utt_id", utt_id)
        projection = self._history.require_projection(normalized_utt)
        links = self._history.links_for_utt(normalized_utt)
        self._require_privileged_reason(access, normalized_utt, instant)
        matched = tuple(
            role
            for link in links
            if self._can_access(link.subject_kind, link.subject_id, access)
            for role in link.roles
        )
        allowed = bool(matched) or self._privileged(access)
        self._audit(
            access=access,
            target_kind="UTT",
            target_id=normalized_utt,
            allowed=allowed,
            at=instant,
        )
        if not allowed:
            raise TransactionAccessDeniedError("principal cannot read this UTT")
        return TransactionHistoryEntry(
            transaction=projection,
            matched_roles=tuple(sorted(set(matched), key=lambda role: role.value)),
        )

    def list_by_continuity_uid(
        self,
        *,
        continuity_uid: str,
        access: TransactionReadContext,
        limit: int = 50,
        cursor: str | None = None,
        at: datetime | None = None,
    ) -> TransactionHistoryPage:
        return self.list_by_subject(
            subject_kind=SubjectKind.CONTINUITY_UID,
            subject_id=continuity_uid,
            access=access,
            limit=limit,
            cursor=cursor,
            at=at,
        )

    def list_by_subject(
        self,
        *,
        subject_kind: SubjectKind,
        subject_id: str,
        access: TransactionReadContext,
        limit: int = 50,
        cursor: str | None = None,
        at: datetime | None = None,
    ) -> TransactionHistoryPage:
        instant = _instant(at)
        if not isinstance(subject_kind, SubjectKind):
            raise TypeError("subject_kind must be a SubjectKind")
        normalized = require_text("subject_id", subject_id).upper()
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        self._require_privileged_reason(access, normalized, instant)
        allowed = self._can_access(subject_kind, normalized, access)
        self._audit(
            access=access,
            target_kind=subject_kind.value,
            target_id=normalized,
            allowed=allowed,
            at=instant,
        )
        if not allowed:
            raise TransactionAccessDeniedError(
                "principal cannot read this subject transaction history"
            )
        rows = list(self._history.list_for_subject(subject_kind, normalized))
        if cursor is not None:
            cursor_key = self._decode_cursor(cursor)
            rows = [
                row
                for row in rows
                if (int(row[0].accepted_at.timestamp()), row[0].utt_id) < cursor_key
            ]
        visible = rows[: limit + 1]
        has_more = len(visible) > limit
        visible = visible[:limit]
        entries = tuple(
            TransactionHistoryEntry(transaction=projection, matched_roles=link.roles)
            for projection, link in visible
        )
        next_cursor = (
            self._encode_cursor(visible[-1][0]) if has_more and visible else None
        )
        return TransactionHistoryPage(entries=entries, next_cursor=next_cursor)

    @staticmethod
    def _privileged(access: TransactionReadContext) -> bool:
        return READ_ANY_PERMISSION in access.permissions

    def _require_privileged_reason(
        self,
        access: TransactionReadContext,
        target_id: str,
        at: datetime,
    ) -> None:
        if self._privileged(access) and (
            access.access_reason is None or not access.access_reason.strip()
        ):
            self._audit(
                access=access,
                target_kind="PRIVILEGED_QUERY",
                target_id=target_id,
                allowed=False,
                at=at,
                fallback_reason="PRIVILEGED_REASON_REQUIRED",
            )
            raise TransactionAccessDeniedError(
                "privileged transaction access requires an access reason"
            )

    def _can_access(
        self,
        kind: SubjectKind,
        subject_id: str,
        access: TransactionReadContext,
    ) -> bool:
        if self._privileged(access):
            return True
        normalized = subject_id.upper()
        if kind is SubjectKind.CONTINUITY_UID:
            return (access.continuity_uid or "").upper() == normalized
        if kind is SubjectKind.MERCHANT_ID:
            return normalized in {value.upper() for value in access.merchant_ids}
        if kind is SubjectKind.BRANCH_ID:
            return normalized in {value.upper() for value in access.branch_ids}
        if kind is SubjectKind.PARTNER_ID:
            return normalized in {value.upper() for value in access.partner_ids}
        return False

    def _audit(
        self,
        *,
        access: TransactionReadContext,
        target_kind: str,
        target_id: str,
        allowed: bool,
        at: datetime,
        fallback_reason: str = "SUBJECT_SCOPED_ACCESS",
    ) -> None:
        principal = require_text("principal_id", access.principal_id)
        reason = (
            access.access_reason.strip()
            if access.access_reason is not None and access.access_reason.strip()
            else fallback_reason
        )
        self._history.append_audit(
            TransactionAccessAudit(
                audit_id=f"TXAUD-{uuid4().hex.upper()}",
                principal_id=principal,
                target_kind=target_kind,
                target_id=target_id,
                outcome=AccessOutcome.ALLOWED if allowed else AccessOutcome.DENIED,
                access_reason=reason,
                occurred_at=at,
            )
        )

    @staticmethod
    def _encode_cursor(projection: UttTransactionProjection) -> str:
        raw = f"{int(projection.accepted_at.timestamp())}|{projection.utt_id}".encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    @staticmethod
    def _decode_cursor(cursor: str) -> tuple[int, str]:
        try:
            padding = "=" * (-len(cursor) % 4)
            decoded = base64.urlsafe_b64decode(cursor + padding).decode("utf-8")
            epoch_raw, utt_id = decoded.split("|", 1)
            if not utt_id.startswith("UTT-"):
                raise ValueError
            return int(epoch_raw), utt_id
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError("invalid transaction-history cursor") from exc
