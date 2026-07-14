"""Verify and exactly-once project signed provider-operation events."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import datetime, timezone

from railone_crypto.canonical_json import canonical_json_bytes
from railone_crypto.signature_service import ArtifactType, SignatureEnvelope, SignatureService

from .models import ProviderOutcomeProjection, ProviderProgressState
from .store import ProviderOutcomeProjectionStore


_STATE_BY_EVENT = {
    "PROVIDER_SUBMISSION_PREPARED": ProviderProgressState.PREPARED,
    "PROVIDER_DISPATCH_STARTED": ProviderProgressState.DISPATCHING,
    "PROVIDER_SUBMISSION_ACCEPTED": ProviderProgressState.ACCEPTED_FOR_PROCESSING,
    "PROVIDER_SUBMISSION_REJECTED": ProviderProgressState.REJECTED,
    "PROVIDER_SUBMISSION_OUTCOME_UNKNOWN": ProviderProgressState.OUTCOME_UNKNOWN,
}


class SignedProviderOutcomeProjector:
    def __init__(
        self,
        *,
        signatures: SignatureService,
        store: ProviderOutcomeProjectionStore,
    ) -> None:
        self._signatures = signatures
        self._store = store

    def project(
        self, envelope: SignatureEnvelope, *, at: datetime | None = None
    ) -> tuple[ProviderOutcomeProjection, bool]:
        verification = self._signatures.verify_artifact(
            envelope, expected_artifact_type=ArtifactType.EXECUTION_EVENT
        )
        if not verification.valid:
            raise PermissionError(f"execution event rejected: {verification.reason}")
        payload = envelope.payload
        event_id = payload.get("event_id")
        event_type = payload.get("event_type")
        if not isinstance(event_id, str) or not event_id:
            raise ValueError("execution event_id is required")
        if event_type not in _STATE_BY_EVENT:
            raise ValueError(f"unsupported provider execution event: {event_type}")
        core = {key: value for key, value in payload.items() if key != "event_id"}
        expected_event_id = "EVT-" + hashlib.sha256(
            canonical_json_bytes(core)
        ).hexdigest().upper()[:32]
        if event_id != expected_event_id:
            raise PermissionError("execution event content identifier mismatch")
        data = payload.get("data")
        if not isinstance(data, Mapping):
            raise ValueError("execution event data must be an object")
        occurred_epoch = payload.get("occurred_at")
        if isinstance(occurred_epoch, bool) or not isinstance(occurred_epoch, int):
            raise ValueError("execution event occurred_at must be an epoch integer")
        instant = at or datetime.now(timezone.utc)
        if instant.tzinfo is None:
            raise ValueError("projection timestamp must be timezone-aware")
        projection = ProviderOutcomeProjection(
            submission_id=str(payload["aggregate_id"]),
            utt_id=str(payload["utt_id"]),
            rtt_id=str(payload["rtt_id"]),
            provider_id=str(payload["provider_id"]),
            state=_STATE_BY_EVENT[event_type],
            normalized_code=data.get("code"),
            external_reference=data.get("external_reference"),
            rejection_disposition=data.get("rejection_disposition"),
            submission_version=int(payload["submission_version"]),
            source_event_id=event_id,
            occurred_at=datetime.fromtimestamp(occurred_epoch, tz=timezone.utc),
            projected_at=instant.astimezone(timezone.utc),
        )
        applied = self._store.apply(
            event_id=event_id,
            event_payload_sha256=str(envelope.protected["payload_sha256"]),
            projection=projection,
        )
        return projection, applied
