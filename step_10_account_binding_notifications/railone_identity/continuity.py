"""Privacy-preserving deterministic RailOne identity continuity."""

from __future__ import annotations

import base64
import hashlib
import hmac
import unicodedata
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from threading import RLock
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

    def get_by_continuity_uid(self, continuity_uid: str) -> IdentityBundle | None:
        ...

    def list_revisions(self, continuity_uid: str) -> tuple[IdentityRevision, ...]:
        ...

    def append_revision(
        self,
        *,
        expected_revision: int,
        bundle: IdentityBundle,
    ) -> None:
        ...


class InMemoryIdentityRepository:
    """Test-only repository modelling the production uniqueness constraint."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._by_fingerprint: dict[str, IdentityBundle] = {}
        self._by_continuity_uid: dict[str, IdentityBundle] = {}
        self._revisions: dict[str, list[IdentityRevision]] = {}

    def get_by_fingerprint(self, fingerprint: str) -> IdentityBundle | None:
        with self._lock:
            return self._by_fingerprint.get(fingerprint)

    def get_by_continuity_uid(self, continuity_uid: str) -> IdentityBundle | None:
        with self._lock:
            return self._by_continuity_uid.get(continuity_uid)

    def list_revisions(self, continuity_uid: str) -> tuple[IdentityRevision, ...]:
        with self._lock:
            return tuple(self._revisions.get(continuity_uid, ()))

    def save(self, bundle: IdentityBundle) -> None:
        with self._lock:
            fingerprint = bundle.genesis.identity_fingerprint
            continuity_uid = bundle.identity.continuity_uid
            if fingerprint in self._by_fingerprint:
                raise ValueError("identity fingerprint already exists")
            if continuity_uid in self._by_continuity_uid:
                raise ValueError("continuity UID already exists")
            self._by_fingerprint[fingerprint] = bundle
            self._by_continuity_uid[continuity_uid] = bundle
            self._revisions[continuity_uid] = [bundle.active_revision]

    def append_revision(
        self,
        *,
        expected_revision: int,
        bundle: IdentityBundle,
    ) -> None:
        with self._lock:
            continuity_uid = bundle.identity.continuity_uid
            current = self._by_continuity_uid.get(continuity_uid)
            if current is None:
                raise LookupError(f"continuity identity not found: {continuity_uid}")
            if current.active_revision.revision != expected_revision:
                raise RuntimeError("identity revision changed concurrently")
            if bundle.active_revision.revision != expected_revision + 1:
                raise ValueError("identity revision must advance exactly once")
            stable_before = (
                current.genesis,
                current.identity.rio_id,
                current.identity.railone_id,
                current.identity.continuity_uid,
                current.identity.rig_id,
                current.identity.corridor,
                current.identity.created_at,
            )
            stable_after = (
                bundle.genesis,
                bundle.identity.rio_id,
                bundle.identity.railone_id,
                bundle.identity.continuity_uid,
                bundle.identity.rig_id,
                bundle.identity.corridor,
                bundle.identity.created_at,
            )
            if stable_before != stable_after:
                raise ValueError("immutable identity anchor fields cannot change")
            if bundle.identity.active_riv_id != bundle.active_revision.riv_id:
                raise ValueError("identity projection must point to the active revision")
            if bundle.identity.status is not bundle.active_revision.status:
                raise ValueError("identity projection status must match active revision")
            if (
                bundle.active_revision.rio_id != bundle.identity.rio_id
                or bundle.active_revision.continuity_uid != continuity_uid
            ):
                raise ValueError("identity revision lineage does not match projection")
            if any(
                revision.attestation_id == bundle.active_revision.attestation_id
                for revision in self._revisions[continuity_uid]
            ):
                raise ValueError("identity attestation was already used by a revision")
            fingerprint = current.genesis.identity_fingerprint
            self._revisions[continuity_uid].append(bundle.active_revision)
            self._by_continuity_uid[continuity_uid] = bundle
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
        instant = self._require_instant(at)
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
                status=IdentityStatus.ACTIVE,
                reason="INITIAL_VERIFIED_ONBOARDING",
                attestation_id=claims["attestation_id"],
                created_at=instant,
            ),
        )
        self._repository.save(bundle)
        return OnboardingResult(bundle, existing=False)

    def get(self, continuity_uid: str) -> IdentityBundle:
        normalized = _normalize(continuity_uid)
        bundle = self._repository.get_by_continuity_uid(normalized)
        if bundle is None:
            raise LookupError(f"continuity identity not found: {normalized}")
        return bundle

    def history(self, continuity_uid: str) -> tuple[IdentityRevision, ...]:
        bundle = self.get(continuity_uid)
        return self._repository.list_revisions(bundle.identity.continuity_uid)

    def revise(
        self,
        *,
        seed: IdentitySeed,
        attestation: SignatureEnvelope,
        status: IdentityStatus,
        reason: str,
        at: datetime | None = None,
    ) -> IdentityBundle:
        """Append a trust revision while preserving the immutable identity anchor."""

        instant = self._require_instant(at)
        normalized_reason = _normalize(reason)
        if not isinstance(status, IdentityStatus):
            raise TypeError("status must be an IdentityStatus")
        seed_payload = seed.canonical_payload()
        validation = self._attestations.verify(
            attestation,
            expected_provider_id=seed_payload["provider_id"],
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

        fingerprint = self._secrets.derive(
            self._continuity_key_id,
            self._DOMAIN + canonical_json_bytes(seed_payload),
        ).hex()
        current = self._repository.get_by_fingerprint(fingerprint)
        if current is None:
            raise LookupError("identity must be onboarded before it can be revised")
        if current.identity.status is IdentityStatus.REVOKED:
            raise PermissionError("revoked identity cannot be revised")

        revision_number = current.active_revision.revision + 1
        riv_id = f"RIV-{current.identity.continuity_uid[5:]}-R{revision_number}"
        revision = IdentityRevision(
            riv_id=riv_id,
            rio_id=current.identity.rio_id,
            continuity_uid=current.identity.continuity_uid,
            revision=revision_number,
            trust_tier=TrustTier(claims["trust_tier"]),
            status=status,
            reason=normalized_reason,
            attestation_id=claims["attestation_id"],
            created_at=instant,
        )
        updated_identity = replace(
            current.identity,
            active_riv_id=riv_id,
            status=status,
        )
        updated = IdentityBundle(
            genesis=current.genesis,
            identity=updated_identity,
            active_revision=revision,
        )
        self._repository.append_revision(
            expected_revision=current.active_revision.revision,
            bundle=updated,
        )
        return updated

    @staticmethod
    def _require_instant(at: datetime | None) -> datetime:
        instant = at or datetime.now(timezone.utc)
        if instant.tzinfo is None:
            raise ValueError("identity timestamp must be timezone-aware")
        return instant.astimezone(timezone.utc)
