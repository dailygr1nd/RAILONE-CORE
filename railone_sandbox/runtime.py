"""Explicit composition root for a synthetic-effects pilot runtime."""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from railone_security import (
    EncryptedAccountEndpointVault, EncryptedContactBindingVault,
    EncryptionPurpose, EnvelopeEncryptionService,
    InMemoryAesGcmKeyEncryptionProvider, InMemoryEncryptedSecretStore,
)
from railone_security.key_provider import KeyEncryptionProvider
from railone_security.store import EncryptedSecretStore

from .effects import SandboxEffectBroker
from .metrics import MetricsRegistry
from .providers import SandboxBankAdapter, SandboxMpesaAdapter
from .store import SandboxEffectStore


@dataclass(frozen=True, slots=True)
class PilotRuntimeConfig:
    mode: str = "SIMULATED_PILOT"
    require_isolated_keys: bool = True

    def validate(self) -> None:
        if self.mode != "SIMULATED_PILOT":
            raise ValueError("Step 11B runtime is restricted to SIMULATED_PILOT mode")


@dataclass(frozen=True, slots=True)
class PilotRuntime:
    config: PilotRuntimeConfig
    account_endpoints: EncryptedAccountEndpointVault
    contact_destinations: EncryptedContactBindingVault
    effects: SandboxEffectBroker
    bank_adapter: SandboxBankAdapter
    mpesa_adapter: SandboxMpesaAdapter
    metrics: MetricsRegistry
    key_boundary: str

    def readiness(self) -> dict[str, object]:
        isolated = self.key_boundary == "ISOLATED"
        ready = self.config.mode == "SIMULATED_PILOT" and (
            isolated or not self.config.require_isolated_keys
        )
        return {
            "status": "READY" if ready else "DEGRADED",
            "runtime_mode": self.config.mode,
            "synthetic_effects_only": True,
            "key_boundary": self.key_boundary,
            "providers": ["BANK-KE", "MPESA-KE"],
        }


def compose_pilot_runtime(
    *, config: PilotRuntimeConfig, keys: KeyEncryptionProvider,
    secret_store: EncryptedSecretStore,
    active_key_ids: dict[EncryptionPurpose, str],
    effect_store: SandboxEffectStore | None = None,
) -> PilotRuntime:
    config.validate()
    encryption = EnvelopeEncryptionService(keys=keys, active_key_ids=active_key_ids)
    metrics = MetricsRegistry()
    effects = SandboxEffectBroker(metrics=metrics, effect_store=effect_store)
    boundary = "SIMULATION_MEMORY" if getattr(keys, "simulation_only", False) else "ISOLATED"
    return PilotRuntime(
        config=config,
        account_endpoints=EncryptedAccountEndpointVault(
            encryption=encryption, store=secret_store
        ),
        contact_destinations=EncryptedContactBindingVault(
            encryption=encryption, store=secret_store
        ),
        effects=effects, bank_adapter=SandboxBankAdapter(effects),
        mpesa_adapter=SandboxMpesaAdapter(effects), metrics=metrics,
        key_boundary=boundary,
    )


def build_local_simulated_runtime() -> PilotRuntime:
    """Developer convenience only; generated keys disappear with the process."""
    keys = InMemoryAesGcmKeyEncryptionProvider()
    active = {}
    for purpose in EncryptionPurpose:
        key_id = f"local-{purpose.value.lower()}-v1"
        keys.register(key_id=key_id, key=secrets.token_bytes(32))
        active[purpose] = key_id
    return compose_pilot_runtime(
        config=PilotRuntimeConfig(require_isolated_keys=False), keys=keys,
        secret_store=InMemoryEncryptedSecretStore(), active_key_ids=active,
    )
