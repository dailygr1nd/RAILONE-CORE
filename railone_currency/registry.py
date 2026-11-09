"""Reference metadata registry: no adapter or execution authority is granted here.

All lookups are descriptive only. The v0.15 routing/dispatch path does not
consult this registry; a later trust boundary must verify issuer, license,
conformance, corridor and external settlement permissions independently.
"""

from __future__ import annotations

from threading import RLock

from .models import CurrencyDefinition, SettlementInstrumentProfile


class CurrencyInstrumentRegistry:
    """In-memory reference for deterministic, append-only metadata versions."""

    def __init__(self) -> None:
        self._currencies: dict[tuple[str, int], CurrencyDefinition] = {}
        self._profiles: dict[tuple[str, int], SettlementInstrumentProfile] = {}
        self._lock = RLock()

    def add_currency(self, definition: CurrencyDefinition) -> CurrencyDefinition:
        key = (definition.currency_code, definition.definition_version)
        with self._lock:
            previous = self._currencies.get(key)
            if previous is not None:
                if previous != definition:
                    raise ValueError("currency revision is immutable")
                return previous
            versions = [version for code, version in self._currencies if code == definition.currency_code]
            if definition.definition_version != (max(versions) + 1 if versions else 1):
                raise ValueError("currency revisions must be appended in sequence")
            self._currencies[key] = definition
            return definition

    def add_profile(self, profile: SettlementInstrumentProfile) -> SettlementInstrumentProfile:
        key = (profile.profile_id, profile.profile_version)
        with self._lock:
            if (profile.currency_code, profile.currency_definition_version) not in self._currencies:
                raise KeyError("profile references an unregistered currency definition revision")
            previous = self._profiles.get(key)
            if previous is not None:
                if previous != profile:
                    raise ValueError("settlement profile revision is immutable")
                return previous
            previous_versions = [item for (name, _), item in self._profiles.items() if name == profile.profile_id]
            if profile.profile_version != (max((item.profile_version for item in previous_versions), default=0) + 1):
                raise ValueError("settlement profile revisions must be appended in sequence")
            # Preserve a profile's enduring identity across revisions. Changing
            # its currency, issuer, instrument or rail requires a new profile ID.
            if previous_versions:
                previous_profile = max(previous_versions, key=lambda item: item.profile_version)
                enduring_fields = (
                    "currency_code", "instrument_kind", "issuer_kind",
                    "issuer_institution_id", "settlement_rail_id", "jurisdiction_country",
                )
                if any(getattr(previous_profile, name) != getattr(profile, name) for name in enduring_fields):
                    raise ValueError("settlement profile identity changed; create a new profile_id")
            self._profiles[key] = profile
            return profile

    def currency(self, currency_code: str, *, version: int | None = None) -> CurrencyDefinition:
        with self._lock:
            options = [item for (code, rev), item in self._currencies.items()
                       if code == currency_code and (version is None or rev == version)]
            if not options:
                raise KeyError("currency definition not registered")
            return max(options, key=lambda item: item.definition_version)

    def profile(self, profile_id: str, *, version: int | None = None) -> SettlementInstrumentProfile:
        with self._lock:
            options = [item for (identifier, rev), item in self._profiles.items()
                       if identifier == profile_id and (version is None or rev == version)]
            if not options:
                raise KeyError("settlement instrument profile not registered")
            return max(options, key=lambda item: item.profile_version)

    def declared_profiles(self, *, currency_code: str) -> tuple[SettlementInstrumentProfile, ...]:
        """Return descriptive metadata, never executable route eligibility."""
        with self._lock:
            identifiers = {profile_id for profile_id, _ in self._profiles}
            latest = (self.profile(profile_id) for profile_id in identifiers)
            return tuple(sorted(
                (item for item in latest if item.currency_code == currency_code),
                key=lambda item: item.profile_id,
            ))
