"""Phase 4: fail-closed institutional SANDBOX dispatch admission.

The gateway has no live-money authority. It independently verifies signed wrapper
bytes and a registry-backed version-pinned adapter, but depends on a trusted
core-backed snapshot reader and economic-fence verifier. Do NOT use self-asserted
snapshots or mock fence services for actual institutional money movement.
"""
from __future__ import annotations

import hmac
from datetime import datetime, timezone
from typing import Protocol

from railone_operations.models import ProviderExecutionRequest

from .models import AdapterCertificationStatus, AdapterEnvironment
from .registry import InstitutionAdapterRegistry
from .spi import InstitutionAdapterBridge
from .wrapper import AuthoritativeDispatchSnapshot, DispatchWrapperService
from .wrapper_store import DispatchWrapperStore


class AuthoritativeSnapshotReader(Protocol):
    """Must construct from independently verified, persisted RailOne records."""
    def load(self, *, rtt_id: str) -> AuthoritativeDispatchSnapshot: ...


class EconomicEffectFenceReader(Protocol):
    """Must read durable/authoritative no-effect evidence and current fence epoch."""
    def assert_dispatch_safe(
        self, *, utt_id: str, rtt_id: str, fence_epoch: int,
        release_evidence_ref: str | None, at: datetime,
    ) -> None: ...


class InstitutionalDispatchAdmissionGateway:
    """The only adapter selection path for INSTITUTIONAL_SANDBOX mode.

    No grant, status, digest, snapshot, or adapter may come from an API caller.
    This is a sandbox integration candidate, NOT a production-authorization gate.
    """

    def __init__(
        self, *, registry: InstitutionAdapterRegistry,
        wrapper_store: DispatchWrapperStore,
        wrapper_verifier: DispatchWrapperService,
        snapshot_reader: AuthoritativeSnapshotReader,
        fence_reader: EconomicEffectFenceReader,
    ) -> None:
        self._registry = registry
        self._wrappers = wrapper_store
        self._verifier = wrapper_verifier
        self._snapshots = snapshot_reader
        self._fences = fence_reader

    def admit(self, request: ProviderExecutionRequest, *, at: datetime) -> InstitutionAdapterBridge:
        if not isinstance(at, datetime) or at.tzinfo is None:
            raise ValueError("institutional dispatch time must be timezone-aware")
        instant = at.astimezone(timezone.utc)
        expected = self._snapshots.load(rtt_id=request.rtt_id)
        signed = self._wrappers.require(request.rtt_id)
        wrapper = self._verifier.verify(signed, expected=expected, at=instant)
        body = wrapper.to_payload()
        trace = body["trace_identifiers"]
        binding = body["execution_binding"]
        terms = body["commercial_terms"]
        checks = (
            (trace["utt_id"], request.utt_id),
            (trace["rtt_id"], request.rtt_id),
            (trace["attempt_number"], request.attempt_number),
            (binding["request_sha256"], request.request_sha256),
            (binding["idempotency_key"], request.idempotency_key),
            (binding["provider_id"], request.provider_id),
            (binding["adapter_binding_ref"], request.adapter_binding_ref),
            (terms["source_amount_minor"], request.amount_minor),
            (terms["receive_amount_minor"], request.receive_amount_minor),
            (terms["source_currency"], request.currency_from),
            (terms["receive_currency"], request.currency_to),
        )
        if any(a != b for a, b in checks):
            raise PermissionError("provider request conflicts with signed canonical wrapper")
        adapter, signed_manifest = self._registry.resolve_with_manifest(
            request.adapter_binding_ref, at=instant
        )
        manifest = signed_manifest.manifest
        if manifest.descriptor.environment not in {AdapterEnvironment.SANDBOX, AdapterEnvironment.PILOT}:
            raise PermissionError("production institutional dispatch is not enabled")
        if manifest.descriptor.certification_status not in {
            AdapterCertificationStatus.CONFORMANCE, AdapterCertificationStatus.CERTIFIED
        }:
            raise PermissionError("institution adapter certification status is ineligible")
        if not hmac.compare_digest(
            str(signed_manifest.signature.protected.get("payload_sha256", "")),
            binding["adapter_manifest_digest"],
        ):
            raise PermissionError("signed wrapper adapter-manifest digest does not match the registry")
        if (manifest.descriptor.provider_id != request.provider_id or
            request.source_institution_id.upper() not in manifest.source_institution_ids or
            request.destination_institution_id.upper() not in manifest.destination_institution_ids or
            request.rail.upper() not in manifest.rails or
            request.currency_from.upper() not in manifest.currencies_from or
            request.currency_to.upper() not in manifest.currencies_to or
            not manifest.min_amount_minor <= request.amount_minor <= manifest.max_amount_minor):
            raise PermissionError("request is outside registered institution capabilities")
        # A wrapper's self-asserted release ref is NEVER sufficient; the fence
        # reader must independently prove no duplicate economic effect is possible.
        fence = body["fencing_controls"]
        self._fences.assert_dispatch_safe(
            utt_id=request.utt_id,
            rtt_id=request.rtt_id,
            fence_epoch=fence["economic_effect_fence_epoch"],
            release_evidence_ref=fence["release_evidence_ref"],
            at=instant,
        )
        return InstitutionAdapterBridge(adapter)
