"""Verified-settlement notification creation and non-duplicating SMS relay."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Protocol

from railone_contracts.store import ContractStore
from railone_crypto.canonical_json import canonical_json_bytes
from railone_crypto.signature_service import ArtifactType, SignatureService
from railone_execution import AttemptState, PlanStatus
from railone_execution.store import ExecutionStore

from .models import (
    NotificationRecipientRole,
    SettlementEvidenceRecord,
    SettlementNotificationResult,
    SmsDeliveryState,
    SmsGatewayResult,
    SmsNotificationRecord,
)
from .store import SettlementNotificationStore


class ContactBindingResolver(Protocol):
    def resolve_sms_destination(self, contact_binding_id: str) -> str: ...


class SmsGateway(Protocol):
    supports_idempotency: bool
    def send(
        self, *, idempotency_key: str, destination: str, body: str
    ) -> SmsGatewayResult: ...


def _content_id(prefix: str, material: object) -> str:
    digest = hashlib.sha256(canonical_json_bytes(material)).hexdigest().upper()
    return f"{prefix}-{digest[:32]}"


def _money(amount_minor: int, currency: str) -> str:
    units, remainder = divmod(amount_minor, 100)
    return f"{currency.upper()} {units:,}.{remainder:02d}"


def _short_utt(utt_id: str) -> str:
    return utt_id[:10] if len(utt_id) > 10 else utt_id


class SettlementNotificationService:
    TEMPLATE_VERSION = "settled-sms-v1"

    def __init__(
        self,
        *,
        signatures: SignatureService,
        contracts: ContractStore,
        executions: ExecutionStore,
        store: SettlementNotificationStore,
        settlement_signing_key_id: str,
        utc_offset_minutes: int = 180,
        timezone_label: str = "EAT",
    ) -> None:
        self._signatures = signatures
        self._contracts = contracts
        self._executions = executions
        self._store = store
        self._key_id = settlement_signing_key_id
        self._offset = utc_offset_minutes
        self._timezone_label = timezone_label

    def confirm_provider_settlement(
        self,
        *,
        utt_id: str,
        provider_id: str,
        provider_transaction_id: str,
        callback_event_id: str,
        at: datetime | None = None,
    ) -> SettlementNotificationResult:
        instant = (at or datetime.now(timezone.utc)).astimezone(timezone.utc)
        signed_utt = self._contracts.require_utt(utt_id)
        if not self._signatures.verify_artifact(
            signed_utt, expected_artifact_type=ArtifactType.UTT
        ).valid:
            raise PermissionError("settlement cannot bind an invalid UTT")
        plan = self._executions.require_plan_for_utt(utt_id)
        if plan.status is not PlanStatus.FINALIZED or plan.previous_rtt_id is None:
            raise PermissionError("settlement notification requires a finalized plan")
        attempt = self._executions.require_attempt(plan.previous_rtt_id)
        if attempt.state is not AttemptState.SUCCEEDED:
            raise PermissionError("settlement notification requires a successful RTT")
        transaction_id = provider_transaction_id.strip()
        callback_id = callback_event_id.strip()
        if not transaction_id or not callback_id:
            raise ValueError("provider settlement references are required")
        evidence_identity = {
            "utt_id": utt_id,
            "utt_payload_sha256": signed_utt.protected["payload_sha256"],
            "provider_id": provider_id,
            "provider_transaction_id": transaction_id,
            "callback_event_id": callback_id,
        }
        evidence_id = _content_id("SET", evidence_identity)
        evidence_core = {
            **evidence_identity,
            "rtt_id": attempt.rtt_id,
            "amount_minor": signed_utt.payload["amount_minor"],
            "currency_from": signed_utt.payload["currency_from"],
            "receive_amount_minor": signed_utt.payload["receive_amount_minor"],
            "currency_to": signed_utt.payload["currency_to"],
            "settled_at": int(instant.timestamp()),
            "evidence_kind": "PROVIDER_CALLBACK_CORRELATED",
        }
        signed = self._signatures.sign_artifact(
            artifact_type=ArtifactType.SETTLEMENT_EVIDENCE,
            payload={"evidence_id": evidence_id, **evidence_core},
            key_id=self._key_id,
            issued_at=instant,
        )
        evidence = SettlementEvidenceRecord(
            evidence_id=evidence_id, utt_id=utt_id, provider_id=provider_id,
            provider_transaction_id=transaction_id, callback_event_id=callback_id,
            signed_evidence=signed, settled_at=instant,
        )
        notifications = self._notifications(evidence, signed_utt.payload, instant)
        stored_evidence, stored_notifications, replayed = self._store.commit_settlement(
            evidence, notifications
        )
        return SettlementNotificationResult(
            stored_evidence, stored_notifications, replayed
        )

    def _notifications(self, evidence, utt, instant):
        local = instant + timedelta(minutes=self._offset)
        rendered_time = f"{local:%d %b %H:%M} {self._timezone_label}"
        payer = utt["payer"]
        beneficiary = utt["beneficiary"]
        sender_body = (
            f"RailOne: SETTLED. {_money(utt['amount_minor'], utt['currency_from'])} "
            f"sent to {beneficiary['display_name']} via "
            f"{beneficiary['endpoint']['institution_display_name']} on {rendered_time}. "
            f"Ref {_short_utt(evidence.utt_id)}. "
            f"Fee {_money(utt['total_fee_minor'], utt['currency_from'])}."
        )
        receiver_body = (
            f"RailOne: SETTLED. You received "
            f"{_money(utt['receive_amount_minor'], utt['currency_to'])} from "
            f"{payer['display_name']} into "
            f"{beneficiary['endpoint']['institution_display_name']} "
            f"{beneficiary['endpoint']['display_hint']} on {rendered_time}. "
            f"Ref {_short_utt(evidence.utt_id)}."
        )
        return (
            self._notification(
                evidence, NotificationRecipientRole.SENDER,
                payer["endpoint"]["contact_binding_id"], sender_body, instant,
            ),
            self._notification(
                evidence, NotificationRecipientRole.RECEIVER,
                beneficiary["endpoint"]["contact_binding_id"], receiver_body, instant,
            ),
        )

    def _notification(self, evidence, role, contact_binding_id, body, instant):
        if len(body) > 320:
            raise ValueError("rendered settlement SMS exceeds two segments")
        body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
        notification_id = _content_id(
            "SMS", {
                "evidence_id": evidence.evidence_id, "recipient_role": role.value,
                "channel": "SMS", "template_version": self.TEMPLATE_VERSION,
            }
        )
        return SmsNotificationRecord(
            notification_id=notification_id, evidence_id=evidence.evidence_id,
            utt_id=evidence.utt_id, recipient_role=role,
            contact_binding_id=contact_binding_id,
            template_version=self.TEMPLATE_VERSION, rendered_body=body,
            body_sha256=body_hash, created_at=instant, updated_at=instant,
        )


class SmsOutboxRelay:
    def __init__(self, *, store: SettlementNotificationStore) -> None:
        self._store = store

    def deliver(
        self,
        *,
        notification_id: str,
        contacts: ContactBindingResolver,
        gateway: SmsGateway,
        at: datetime | None = None,
    ) -> SmsNotificationRecord:
        instant = (at or datetime.now(timezone.utc)).astimezone(timezone.utc)
        record = self._store.require_notification(notification_id)
        if record.state in {
            SmsDeliveryState.SENT, SmsDeliveryState.REJECTED, SmsDeliveryState.UNKNOWN
        }:
            return record
        if record.state is SmsDeliveryState.DISPATCHING:
            return self._finish(
                record, SmsDeliveryState.UNKNOWN,
                "NON_IDEMPOTENT_SMS_RECOVERY_BLOCKED", None, instant,
            )
        dispatching = replace(
            record, state=SmsDeliveryState.DISPATCHING,
            version=record.version + 1, updated_at=instant,
        )
        self._store.transition_notification(
            previous_version=record.version, notification=dispatching
        )
        try:
            destination = contacts.resolve_sms_destination(record.contact_binding_id)
            result = gateway.send(
                idempotency_key=record.notification_id,
                destination=destination,
                body=record.rendered_body,
            )
        except Exception:
            return self._finish(
                dispatching, SmsDeliveryState.UNKNOWN,
                "SMS_GATEWAY_OUTCOME_UNKNOWN", None, instant,
            )
        return self._finish(
            dispatching,
            SmsDeliveryState.SENT if result.accepted else SmsDeliveryState.REJECTED,
            result.code, result.gateway_reference, instant,
        )

    def _finish(self, record, state, code, reference, instant):
        updated = replace(
            record, state=state, normalized_code=code.upper(),
            gateway_reference=reference, version=record.version + 1,
            updated_at=instant,
        )
        self._store.transition_notification(
            previous_version=record.version, notification=updated
        )
        return updated
