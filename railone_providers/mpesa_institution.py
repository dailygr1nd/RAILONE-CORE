"""Step 11D capability profile for the existing M-PESA B2C submission adapter."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from railone_institutions.legacy import ProviderAdapterInstitutionPlugin
from railone_institutions.models import (
    AdapterCertificationStatus,
    AdapterDescriptor,
    AdapterEnvironment,
    FinalityLevel,
    InstitutionAuthProfile,
    InstitutionCapabilityManifest,
    InstitutionOperation,
    MessageStandard,
    TransportKind,
)

from .mpesa import MpesaB2CAdapter


def mpesa_b2c_institution_plugin(
    adapter: MpesaB2CAdapter,
    *,
    source_institution_ids: tuple[str, ...],
    destination_institution_ids: tuple[str, ...],
    now: datetime | None = None,
) -> ProviderAdapterInstitutionPlugin:
    instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    descriptor = AdapterDescriptor(
        adapter_id="railone.mpesa.ke.b2c",
        adapter_version="1.0.0",
        provider_id="MPESA-KE",
        network_id="SAFARICOM-DARAJA-B2C",
        environment=AdapterEnvironment.SANDBOX,
        transport=TransportKind.HTTPS,
        message_standard=MessageStandard.JSON,
        auth_profile=InstitutionAuthProfile.OAUTH2_CLIENT_CREDENTIALS,
        certification_status=AdapterCertificationStatus.CONFORMANCE,
    )
    manifest = InstitutionCapabilityManifest(
        manifest_id="manifest.railone.mpesa.ke.b2c",
        manifest_version=1,
        descriptor=descriptor,
        source_institution_ids=source_institution_ids,
        destination_institution_ids=destination_institution_ids,
        source_countries=("KE",), destination_countries=("KE",),
        rails=("MOBILE_MONEY",), currencies_from=("KES",), currencies_to=("KES",),
        operations=(InstitutionOperation.SUBMIT,),
        supports_idempotency=False,
        supports_callbacks=False,
        supports_active_status=False,
        supports_reconciliation=False,
        asserted_finality=FinalityLevel.PROCESSING,
        min_amount_minor=100,
        max_amount_minor=25_000_000_00,
        request_timeout_seconds=adapter.request_timeout_seconds,
        issued_at=instant, expires_at=instant + timedelta(days=30),
    )
    return ProviderAdapterInstitutionPlugin(adapter=adapter, descriptor=descriptor, manifest=manifest)
