"""Atomic PostgreSQL settlement-evidence and SMS-outbox store."""

from __future__ import annotations

from railone_crypto.signature_service import SignatureEnvelope
from railone_notifications import (
    NotificationRecipientRole, SettlementConflictError, SettlementEvidenceRecord,
    SettlementNotificationStore, SmsDeliveryState, SmsNotificationRecord,
)
from railone_security import EncryptedEnvelope, NotificationBodyProtector

from .codec import envelope_from_db, json_object, json_text
from .runtime import PostgresDatabase


_NOTIFICATION_COLUMNS = """notification_id, evidence_id, utt_id, recipient_role,
contact_binding_id, template_version, rendered_body, body_sha256, state,
gateway_reference, normalized_code, version, created_at, updated_at,
rendered_body_envelope, body_encryption_key_id, body_envelope_version"""

_ENCRYPTED_BODY_PLACEHOLDER = "[ENCRYPTED]"


class PostgresSettlementNotificationStore(SettlementNotificationStore):
    def __init__(
        self, database: PostgresDatabase,
        *, body_protector: NotificationBodyProtector | None = None,
        require_encrypted_bodies: bool = False,
    ) -> None:
        if require_encrypted_bodies and body_protector is None:
            raise ValueError("deployed notification store requires body encryption")
        self._database = database
        self._body_protector = body_protector

    def commit_settlement(self, evidence, notifications):
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO railone.settlement_evidence
                   (evidence_id, utt_id, provider_id, provider_transaction_id,
                    callback_event_id, signed_evidence, evidence_payload_sha256,
                    settled_at)
                   VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s)
                   ON CONFLICT (utt_id) DO NOTHING RETURNING evidence_id""",
                (
                    evidence.evidence_id, evidence.utt_id, evidence.provider_id,
                    evidence.provider_transaction_id, evidence.callback_event_id,
                    json_text(evidence.signed_evidence.to_dict()),
                    evidence.signed_evidence.protected["payload_sha256"],
                    evidence.settled_at,
                ),
            )
            inserted = cursor.fetchone() is not None
            if not inserted:
                cursor.execute(
                    """SELECT evidence_id, utt_id, provider_id,
                              provider_transaction_id, callback_event_id,
                              signed_evidence, settled_at
                       FROM railone.settlement_evidence WHERE utt_id=%s""",
                    (evidence.utt_id,),
                )
                row = cursor.fetchone()
                if row is None or row["evidence_id"] != evidence.evidence_id:
                    raise SettlementConflictError(
                        "UTT received conflicting settlement evidence"
                    )
                stored_evidence = _evidence(row)
            else:
                stored_evidence = evidence
                for notification in notifications:
                    cursor.execute(
                        f"""INSERT INTO railone.sms_notification_outbox
                            ({_NOTIFICATION_COLUMNS})
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        _notification_params(notification, self._body_protector),
                    )
            rows = []
            for notification in notifications:
                cursor.execute(
                    f"""SELECT {_NOTIFICATION_COLUMNS}
                        FROM railone.sms_notification_outbox
                        WHERE notification_id=%s""",
                    (notification.notification_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError("settlement notification commit was incomplete")
                rows.append(_notification(row, self._body_protector))
            return stored_evidence, tuple(rows), not inserted

    def require_notification(self, notification_id):
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {_NOTIFICATION_COLUMNS} FROM railone.sms_notification_outbox WHERE notification_id=%s",
                (notification_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise LookupError("SMS notification not found")
            return _notification(row, self._body_protector)

    def transition_notification(self, *, previous_version, notification):
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """UPDATE railone.sms_notification_outbox
                   SET state=%s, gateway_reference=%s, normalized_code=%s,
                       version=%s, updated_at=%s
                   WHERE notification_id=%s AND version=%s
                     AND state NOT IN ('SENT','REJECTED','UNKNOWN')""",
                (
                    notification.state.value, notification.gateway_reference,
                    notification.normalized_code, notification.version,
                    notification.updated_at, notification.notification_id,
                    previous_version,
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("SMS notification changed concurrently")

    def pending_notifications(self, *, limit=100):
        if isinstance(limit, bool) or not 1 <= limit <= 1000:
            raise ValueError("notification limit is outside policy")
        with self._database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""SELECT {_NOTIFICATION_COLUMNS}
                    FROM railone.sms_notification_outbox
                    WHERE state IN ('PREPARED','DISPATCHING')
                    ORDER BY created_at, notification_id LIMIT %s""",
                (limit,),
            )
            return tuple(
                _notification(row, self._body_protector) for row in cursor.fetchall()
            )


def _evidence(row):
    return SettlementEvidenceRecord(
        evidence_id=str(row["evidence_id"]), utt_id=str(row["utt_id"]),
        provider_id=str(row["provider_id"]),
        provider_transaction_id=str(row["provider_transaction_id"]),
        callback_event_id=str(row["callback_event_id"]),
        signed_evidence=envelope_from_db(row["signed_evidence"]),
        settled_at=row["settled_at"],
    )


def _notification_params(value, protector):
    envelope = None
    rendered_body = value.rendered_body
    if protector is not None:
        envelope = protector.protect(
            notification_id=value.notification_id, utt_id=value.utt_id,
            body=value.rendered_body,
        )
        rendered_body = _ENCRYPTED_BODY_PLACEHOLDER
    return (
        value.notification_id, value.evidence_id, value.utt_id,
        value.recipient_role.value, value.contact_binding_id,
        value.template_version, rendered_body, value.body_sha256,
        value.state.value, value.gateway_reference, value.normalized_code,
        value.version, value.created_at, value.updated_at,
        json_text(envelope.to_dict()) if envelope is not None else None,
        envelope.key_id if envelope is not None else None,
        envelope.version if envelope is not None else None,
    )


def _notification(row, protector):
    body = str(row["rendered_body"])
    encrypted = row.get("rendered_body_envelope")
    if encrypted is not None:
        if protector is None:
            raise RuntimeError("notification body is encrypted but no protector is configured")
        envelope = EncryptedEnvelope.from_dict(json_object(encrypted))
        if row.get("body_encryption_key_id") != envelope.key_id:
            raise PermissionError("notification body key metadata mismatch")
        if int(row.get("body_envelope_version")) != envelope.version:
            raise PermissionError("notification body version metadata mismatch")
        body = protector.reveal(
            notification_id=str(row["notification_id"]), utt_id=str(row["utt_id"]),
            envelope=envelope, expected_sha256=str(row["body_sha256"]),
        )
    return SmsNotificationRecord(
        notification_id=str(row["notification_id"]),
        evidence_id=str(row["evidence_id"]), utt_id=str(row["utt_id"]),
        recipient_role=NotificationRecipientRole(row["recipient_role"]),
        contact_binding_id=str(row["contact_binding_id"]),
        template_version=str(row["template_version"]),
        rendered_body=body,
        body_sha256=str(row["body_sha256"]), state=SmsDeliveryState(row["state"]),
        gateway_reference=row["gateway_reference"],
        normalized_code=row["normalized_code"], version=int(row["version"]),
        created_at=row["created_at"], updated_at=row["updated_at"],
    )
