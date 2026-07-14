"""Verified, deterministic registry for version-pinned institution adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock

from .manifest import CapabilityManifestSigner
from .models import AdapterCertificationStatus, InstitutionCapabilityManifest, SignedCapabilityManifest
from .spi import InstitutionAdapter, InstitutionAdapterBridge


@dataclass(frozen=True, slots=True)
class AdapterEligibilityQuery:
    source_institution_id: str
    destination_institution_id: str
    source_country: str
    destination_country: str
    rail: str
    currency_from: str
    currency_to: str
    amount_minor: int


class InstitutionAdapterRegistry:
    """Routes may discover eligible adapters, but an RTT must pin one exact version."""

    def __init__(self, verifier: CapabilityManifestSigner) -> None:
        self._verifier = verifier
        self._entries: dict[str, tuple[InstitutionAdapter, SignedCapabilityManifest]] = {}
        self._lock = RLock()

    def register(self, adapter: InstitutionAdapter, signed: SignedCapabilityManifest) -> None:
        self._verifier.verify(signed)
        if adapter.descriptor != signed.manifest.descriptor:
            raise ValueError("adapter descriptor does not match signed manifest")
        if adapter.capabilities().to_payload() != signed.manifest.to_payload():
            raise ValueError("adapter capabilities do not match signed manifest")
        ref = adapter.descriptor.binding_ref
        with self._lock:
            existing = self._entries.get(ref)
            if existing is not None and existing[1].signature.signature != signed.signature.signature:
                raise ValueError("binding reference already registered with different signed capabilities")
            self._entries[ref] = (adapter, signed)

    def resolve(self, binding_ref: str, *, at: datetime | None = None) -> InstitutionAdapter:
        instant = (at or datetime.now(timezone.utc)).astimezone(timezone.utc)
        with self._lock:
            entry = self._entries.get(binding_ref)
        if entry is None:
            raise KeyError(f"institution adapter binding not found: {binding_ref}")
        adapter, signed = entry
        if not signed.manifest.is_active_at(instant):
            raise PermissionError("institution adapter manifest is inactive or expired")
        if signed.manifest.descriptor.certification_status is AdapterCertificationStatus.DRAFT:
            raise PermissionError("draft institution adapter cannot execute")
        return adapter

    def provider_bridge(
        self, binding_ref: str, *, at: datetime | None = None
    ) -> InstitutionAdapterBridge:
        """Return the legacy coordinator contract for one exact registered version."""
        return InstitutionAdapterBridge(self.resolve(binding_ref, at=at))

    def eligible(self, query: AdapterEligibilityQuery, *, at: datetime | None = None) -> tuple[InstitutionAdapter, ...]:
        instant = (at or datetime.now(timezone.utc)).astimezone(timezone.utc)
        with self._lock:
            entries = tuple(self._entries.values())
        matched: list[InstitutionAdapter] = []
        for adapter, signed in entries:
            manifest = signed.manifest
            if not manifest.is_active_at(instant) or manifest.descriptor.certification_status is AdapterCertificationStatus.DRAFT:
                continue
            if (
                query.source_institution_id.upper() in manifest.source_institution_ids
                and query.destination_institution_id.upper() in manifest.destination_institution_ids
                and query.source_country.upper() in manifest.source_countries
                and query.destination_country.upper() in manifest.destination_countries
                and query.rail.upper() in manifest.rails
                and query.currency_from.upper() in manifest.currencies_from
                and query.currency_to.upper() in manifest.currencies_to
                and manifest.min_amount_minor <= query.amount_minor <= manifest.max_amount_minor
            ):
                matched.append(adapter)
        return tuple(sorted(matched, key=lambda item: (item.descriptor.priority, item.descriptor.binding_ref)))
