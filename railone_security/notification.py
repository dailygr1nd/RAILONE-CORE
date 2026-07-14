"""Encryption boundary for persisted notification bodies."""

from __future__ import annotations

import hashlib

from .envelope import EnvelopeEncryptionService, EnvelopeIntegrityError
from .models import EncryptedEnvelope, EncryptionPurpose


class NotificationBodyProtector:
    def __init__(self, encryption: EnvelopeEncryptionService) -> None:
        self._encryption = encryption

    def protect(self, *, notification_id: str, utt_id: str, body: str) -> EncryptedEnvelope:
        return self._encryption.encrypt_text(
            purpose=EncryptionPurpose.NOTIFICATION_BODY,
            record_id=notification_id, owner_id=utt_id,
            field_name="rendered_body", plaintext=body,
        )

    def reveal(
        self, *, notification_id: str, utt_id: str,
        envelope: EncryptedEnvelope, expected_sha256: str,
    ) -> str:
        body = self._encryption.decrypt_text(
            envelope=envelope, purpose=EncryptionPurpose.NOTIFICATION_BODY,
            record_id=notification_id, owner_id=utt_id,
            field_name="rendered_body",
        )
        actual = hashlib.sha256(body.encode("utf-8")).hexdigest()
        if actual != expected_sha256:
            raise EnvelopeIntegrityError("notification body fingerprint mismatch")
        return body
