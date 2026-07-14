"""Privacy-preserving deterministic RailOne identity continuity."""

from __future__ import annotations

import base64
import hashlib
import hmac
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from railone_crypto.canonical_json import canonical_json_bytes
from railone_crypto.signature_service import SignatureEnvelope

from .attestation import IdentityAttestationVerifier
from .models import (
    IdentityBundle,
    IdentityGenesis,
    IdentityObject,
    IdentityRevision,
    IdentityStatus,
    TrustTier,
)


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip().upper()
    if not normalized:
        raise ValueError("identity seed value cannot be empty")
    return normalized


@dataclass(frozen=True, slots=True)
class IdentitySeed:
    provider_id: str
    provider_subject_reference: str = field(repr=False)
    country_code: str

    def canonical_payload(self) -> dict[str, str]:
        return {
            "provider_id": _normalize(self.provider_id),
            "provider_subject_reference": _normalize(
                self.provider_subject_reference
            ),
            "country_code": _normalize(self.country_code),
        }


class ContinuitySecretProvider(Protocol):
    def derive(self, key_id: str, message: bytes) -> bytes:
        ...


class InMemoryContinuitySecretProvider:
    """Test-only HMAC provider; production keys belong in an isolated service."""

    def __init__(self) -> None:
        self._secrets: dict[str, bytes] = {}

    def register(self, key_id: str, secret: bytes) -> None:
        if len(secret) < 32:
            raise ValueError("continuity secret must contain at least 32 bytes")
        if key_id in self._secrets:
            raise ValueError(f"duplicate continuity key: {key_id}")
        self._secrets[key_id] = secret

    def derive(self, key_id: str, message: bytes) -> bytes:
        secret = self._secrets.get(key_id)
        if secret is None:
            raise KeyError(f"continuity key not found: {key_id}")
        return hmac.new(secret, message, hashlib.sha256).digest()


class IdentityRepository(Protocol):
    def get_by_fingerprint(self, fingerprint: str) -> IdentityBundle | None:
        ...

    def save(self, bundle: IdentityBundle) -> None:
        ...


class InMemoryIdentityRepository:
    """Test-only repository modelling the production uniqueness constraint."""

    def __init__(self) -> None:
        self._by_fingerprint: dict[str, IdentityBundle] = {}

    def get_by_fingerprint(self, fingerprint: str) -> IdentityBundle | None:
        return self._by_fingerprint.get(fingerprint)

    def save(self, bundle: IdentityBundle) -> None:
        fingerprint = bundle.genesis.identity_fingerprint
        if fingerprint in self._by_fingerprint:
            raise ValueError("identity fingerprint already exists")
        self._by_fingerprint[fingerprint] = bundle


@dataclass(frozen=True, slots=True)
class OnboardingResult:
    bundle: IdentityBundle
    existing: bool


class IdentityContinuityService:
    _DOMAIN = b"RAILONE-IDENTITY-CONTINUITY-V1\x00"

    def __init__(
        self,
        *,
        continuity_key_id: str,
        secrets: ContinuitySecretProvider,
        attestations: IdentityAttestationVerifier,
        repository: IdentityRepository,
    ) -> None:
        self._continuity_key_id = continuity_key_id
        self._secrets = secrets
        self._attestations = attestations
        self._repository = repository

    def onboard(
        self,
        *,
        seed: IdentitySeed,
        attestation: SignatureEnvelope,
        corridor: str,
        at: datetime | None = None,
    ) -> OnboardingResult:
        instant = (at or datetime.now(timezone.utc)).astimezone(timezone.utc)
        seed_payload = seed.canonical_payload()
        provider_id = seed_payload["provider_id"]
        validation = self._attestations.verify(
            attestation,
            expected_provider_id=provider_id,
            at=instant,
        )
        if not validation.valid or validation.claims is None:
            raise PermissionError(f"identity attestation rejected: {validation.reason}")

        claims = validation.claims
        if _normalize(claims["provider_subject_reference"]) != seed_payload[
            "provider_subject_reference"
        ]:
            raise PermissionError("identity attestation subject mismatch")
        if _normalize(claims["country_code"]) != seed_payload["country_code"]:
            raise PermissionError("identity attestation country mismatch")

        digest = self._secrets.derive(
            self._continuity_key_id,
            self._DOMAIN + canonical_json_bytes(seed_payload),
        )
        fingerprint = digest.hex()
        existing = self._repository.get_by_fingerprint(fingerprint)
        if existing is not None:
            return OnboardingResult(existing, existing=True)

        continuity_segment = base64.b32encode(digest[:20]).decode("ascii").rstrip("=")
        continuity_uid = f"CUID-{continuity_segment}"
        normalized_corridor = _normalize(corridor)
        rig_id = f"RIG-{continuity_segment}"
        rio_id = f"RIO-{continuity_segment}"
        riv_id = f"RIV-{continuity_segment}-R1"
        railone_id = f"R1-{normalized_corridor}-{continuity_segment}"
        trust_tier = TrustTier(claims["trust_tier"])

        bundle = IdentityBundle(
            genesis=IdentityGenesis(
                rig_id=rig_id,
                continuity_uid=continuity_uid,
                continuity_key_id=self._continuity_key_id,
                identity_fingerprint=fingerprint,
                verification_provider_id=provider_id,
                verification_reference=claims["verification_reference"],
                evidence_sha256=claims["evidence_sha256"],
                attestation_id=claims["attestation_id"],
                created_at=instant,
            ),
            identity=IdentityObject(
                rio_id=rio_id,
                railone_id=railone_id,
                continuity_uid=continuity_uid,
                rig_id=rig_id,
                active_riv_id=riv_id,
                corridor=normalized_corridor,
                status=IdentityStatus.ACTIVE,
                created_at=instant,
            ),
            active_revision=IdentityRevision(
                riv_id=riv_id,
                rio_id=rio_id,
                continuity_uid=continuity_uid,
                revision=1,
                trust_tier=trust_tier,
                reason="INITIAL_VERIFIED_ONBOARDING",
                attestation_id=claims["attestation_id"],
                created_at=instant,
            ),
        )
        self._repository.save(bundle)
        return OnboardingResult(bundle, existing=False)
