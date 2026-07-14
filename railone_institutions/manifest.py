"""Ed25519 signing and verification for institution capability declarations."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone

from railone_crypto.signature_service import ArtifactType, SignatureEnvelope, SignatureService

from .models import InstitutionCapabilityManifest, SignedCapabilityManifest


class CapabilityManifestSigner:
    def __init__(self, signatures: SignatureService, *, signing_key_id: str) -> None:
        self._signatures = signatures
        self._signing_key_id = signing_key_id

    def sign(self, manifest: InstitutionCapabilityManifest, *, issued_at: datetime | None = None) -> SignedCapabilityManifest:
        envelope = self._signatures.sign_artifact(
            artifact_type=ArtifactType.INSTITUTION_CAPABILITY_MANIFEST,
            payload=manifest.to_payload(),
            key_id=self._signing_key_id,
            issued_at=issued_at,
        )
        return SignedCapabilityManifest(manifest=manifest, signature=envelope)

    def verify(self, signed: SignedCapabilityManifest) -> None:
        check = self._signatures.verify_artifact(
            signed.signature,
            expected_artifact_type=ArtifactType.INSTITUTION_CAPABILITY_MANIFEST,
        )
        if not check.valid:
            raise PermissionError(f"capability manifest signature rejected: {check.reason}")
        if signed.signature.to_dict()["payload"] != signed.manifest.to_payload():
            raise PermissionError("capability manifest object does not match signed payload")
        signed_at = datetime.fromtimestamp(
            int(signed.signature.protected["iat"]), tz=timezone.utc
        )
        if not signed.manifest.issued_at <= signed_at < signed.manifest.expires_at:
            raise PermissionError("capability manifest signature is outside its validity window")


def envelope_from_dict(value: dict[str, object]) -> SignatureEnvelope:
    return SignatureEnvelope.from_dict(value)
