"""Deployable simulated-pilot infrastructure composition.

Signing remains an injected trust boundary. This module composes persistence,
confidentiality, synthetic effects and worker supervision without creating or
loading signing private keys.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from railone_crypto.signature_service import SignatureService
from railone_institutions import InstitutionAdapterRegistry, InstitutionalDispatchAdmissionGateway
from railone_institutions.wrapper import DispatchWrapperService
from railone_operations import ProviderSubmissionCoordinator
from railone_postgres import (
    MigrationRunner, PostgresCallbackInboxStore, PostgresCertificationReportStore,
    PostgresCertificationRunRecorder,
    PostgresContractStore,
    PostgresDatabase, PostgresDispatchWrapperStore, PostgresEconomicEffectFence,
    PostgresEncryptedSecretStore, PostgresExecutionStore,
    PostgresIdentityRepository, PostgresInstitutionManifestStore,
    PostgresOperationsStore,
    PostgresPartnerDirectory, PostgresProviderOutcomeProjectionStore,
    PostgresSandboxEffectStore, PostgresSettlementNotificationStore,
    PostgresTransactionHistoryStore, psycopg_connection_factory,
)
from railone_postgres.dispatch_snapshot import PostgresDispatchSnapshotReader
from railone_postgres.security_incidents import PostgresSecurityAuditStore
from railone_postgres.runtime import ConnectionFactory
from railone_security import (
    EncryptedAccountEndpointVault, EncryptedContactBindingVault,
    EncryptedProviderCredentialVault, EncryptionPurpose,
    EnvelopeEncryptionService, IsolatedKeyServiceClient,
    NotificationBodyProtector, RemoteKeyEncryptionProvider,
)

from .effects import SandboxEffectBroker
from .metrics import MetricsRegistry
from .providers import SandboxBankAdapter, SandboxMpesaAdapter
from .workers import (
    ProviderEffectConsumer, SandboxEffectWorker, SupervisorState,
    WorkerSupervisor,
)


@dataclass(frozen=True, slots=True)
class DeployedSandboxConfig:
    database_url: str
    migrations_directory: Path
    account_endpoint_key_id: str
    contact_destination_key_id: str
    provider_credential_key_id: str
    notification_body_key_id: str
    worker_id: str
    runtime_mode: str = "SIMULATED_PILOT"

    @classmethod
    def from_environment(
        cls, environ: Mapping[str, str] | None = None,
        *, repository_root: Path | None = None,
    ) -> "DeployedSandboxConfig":
        values = os.environ if environ is None else environ
        root = repository_root or Path(__file__).resolve().parents[1]
        return cls(
            database_url=values.get("RAILONE_DATABASE_URL", ""),
            migrations_directory=Path(
                values.get("RAILONE_MIGRATIONS_DIRECTORY", str(root / "migrations"))
            ),
            account_endpoint_key_id=values.get("RAILONE_ACCOUNT_ENDPOINT_KEK_ID", ""),
            contact_destination_key_id=values.get("RAILONE_CONTACT_DESTINATION_KEK_ID", ""),
            provider_credential_key_id=values.get("RAILONE_PROVIDER_CREDENTIAL_KEK_ID", ""),
            notification_body_key_id=values.get("RAILONE_NOTIFICATION_BODY_KEK_ID", ""),
            worker_id=values.get("RAILONE_SANDBOX_EFFECT_WORKER_ID", ""),
            runtime_mode=values.get("RAILONE_RUNTIME_MODE", ""),
        )

    def validate(self) -> None:
        if self.runtime_mode != "SIMULATED_PILOT":
            raise ValueError("deployable Step 11E runtime is simulation-only")
        required = {
            "database_url": self.database_url,
            "account_endpoint_key_id": self.account_endpoint_key_id,
            "contact_destination_key_id": self.contact_destination_key_id,
            "provider_credential_key_id": self.provider_credential_key_id,
            "notification_body_key_id": self.notification_body_key_id,
            "worker_id": self.worker_id,
        }
        missing = [name for name, value in required.items() if not value.strip()]
        if missing:
            raise ValueError("missing deployed sandbox configuration: " + ", ".join(missing))
        if not self.migrations_directory.is_dir():
            raise ValueError("RailOne migrations directory is unavailable")


@dataclass(frozen=True, slots=True)
class DeployedSandboxRuntime:
    config: DeployedSandboxConfig
    database: PostgresDatabase
    migrations: MigrationRunner
    identity: PostgresIdentityRepository
    contracts: PostgresContractStore
    executions: PostgresExecutionStore
    operations: PostgresOperationsStore
    institution_manifests: PostgresInstitutionManifestStore
    certification_reports: PostgresCertificationReportStore
    certification_runs: PostgresCertificationRunRecorder
    history: PostgresTransactionHistoryStore
    projections: PostgresProviderOutcomeProjectionStore
    callbacks: PostgresCallbackInboxStore
    partners: PostgresPartnerDirectory
    notifications: PostgresSettlementNotificationStore
    account_endpoints: EncryptedAccountEndpointVault
    contact_destinations: EncryptedContactBindingVault
    provider_credentials: EncryptedProviderCredentialVault
    effects: SandboxEffectBroker
    bank_adapter: SandboxBankAdapter
    mpesa_adapter: SandboxMpesaAdapter
    supervisor: WorkerSupervisor
    metrics: MetricsRegistry
    connection_factory: ConnectionFactory

    def apply_migrations(self) -> None:
        self.migrations.apply_all()

    def sender_first_p2p_acceptance(
        self, *, signatures: SignatureService,
        utt_signing_key_id: str, authority_signing_key_id: str,
    ):
        """Strict sandbox acceptance boundary: ETK-S precedes ETK-R and UTT.

        The caller must supply independently authenticated P2P signing keys.
        This method does not expose or generate those private keys.
        """
        from railone_authority.service import ExecutionAuthorityService
        from railone_contracts.acceptance_service import QuoteAcceptanceService
        return QuoteAcceptanceService(
            signatures=signatures, authority=ExecutionAuthorityService(signatures),
            store=self.contracts, utt_signing_key_id=utt_signing_key_id,
            authority_signing_key_id=authority_signing_key_id,
            require_bilateral_p2p=True,
            security_audit=PostgresSecurityAuditStore(self.database),
        )

    def authenticated_p2p_facade(
        self, *, signatures: SignatureService, access_tokens,
        utt_signing_key_id: str, authority_signing_key_id: str,
        api_audit_signing_key_id: str, enable_avia_merchant: bool = False,
    ):
        """Compose the strict sender-first API atop durable PostgreSQL stores.

        AccessTokenService is injected and must have a trusted issuer,
        key provider, and durable token-revocation store. This method neither
        provisions user keys nor mints a bearer token.
        """
        from railone_api import (
            AuthenticatedRequestGuard, BilateralP2PApi, RailOneApiFacade,
        )
        from railone_authority.bilateral import BilateralAuthorityService
        from railone_history import TransactionHistoryService
        from railone_postgres import PostgresApiAuditStore, PostgresRateLimitStore
        from railone_api.avia import AviaMerchantApi
        acceptance = self.sender_first_p2p_acceptance(
            signatures=signatures, utt_signing_key_id=utt_signing_key_id,
            authority_signing_key_id=authority_signing_key_id)
        return RailOneApiFacade(
            guard=AuthenticatedRequestGuard(
                tokens=access_tokens,
                rate_limits=PostgresRateLimitStore(self.database),
                audits=PostgresApiAuditStore(self.database),
                signatures=signatures,
                audit_signing_key_id=api_audit_signing_key_id,
            ),
            history=TransactionHistoryService(self.history),
            outcomes=self.projections,
            avia_merchant=AviaMerchantApi(acceptance) if enable_avia_merchant else None,
            bilateral_p2p=BilateralP2PApi(
                bilateral=BilateralAuthorityService(signatures),
                acceptance=acceptance,
            ),
        )

    def institutional_dispatcher(
        self, *, signatures: SignatureService, registry: InstitutionAdapterRegistry,
        event_signing_key_id: str, wrapper_signing_key_id: str,
        trusted_no_effect_signing_keys: frozenset[str], core_owner_id: str = "RAILONE",
        require_sender_first: bool = True,
    ) -> ProviderSubmissionCoordinator:
        """Compose an internal sandbox dispatcher for provisioned signed instructions."""
        verifier = DispatchWrapperService(
            signatures, signing_key_id=wrapper_signing_key_id,
            expected_core_owner_id=core_owner_id,
        )
        gateway = InstitutionalDispatchAdmissionGateway(
            registry=registry,
            wrapper_store=PostgresDispatchWrapperStore(self.database, verifier),
            wrapper_verifier=verifier,
            snapshot_reader=PostgresDispatchSnapshotReader(
                self.database, signatures=signatures, core_owner_id=core_owner_id,
                require_sender_first=require_sender_first,
            ),
            allow_pilot_adapters=False,
            security_audit=(PostgresSecurityAuditStore(self.database)
                            if require_sender_first else None),
            fence_reader=PostgresEconomicEffectFence(
                self.database, signatures=signatures,
                trusted_no_effect_signing_keys=trusted_no_effect_signing_keys,
            ),
        )
        return ProviderSubmissionCoordinator(
            signatures=signatures, contracts=self.contracts, executions=self.executions,
            operations=self.operations, endpoint_resolver=self.account_endpoints,
            event_signing_key_id=event_signing_key_id, dispatch_mode="INSTITUTIONAL_SANDBOX",
            institutional_admission=gateway,
        )

    def readiness(self) -> dict[str, object]:
        checks: dict[str, str] = {
            "runtime_mode": "UP" if self.config.runtime_mode == "SIMULATED_PILOT" else "DOWN",
            "key_boundary": "UP",
            "synthetic_effects_only": "UP",
        }
        try:
            connection = self.connection_factory()
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT version FROM railone.schema_migrations ORDER BY version DESC LIMIT 1"
                    )
                    row = cursor.fetchone()
                checks["postgres"] = "UP"
                latest = str(row["version"]) if row is not None else ""
                checks["migration_0010"] = (
                    "UP" if latest.isdigit() and int(latest) >= 10 else "DOWN"
                )
                checks["migration_0016"] = (
                    "UP" if latest.isdigit() and int(latest) >= 16 else "DOWN"
                )
            finally:
                connection.close()
        except Exception:
            checks["postgres"] = "DOWN"
            checks["migration_0010"] = "DOWN"
            checks["migration_0016"] = "DOWN"
        supervisor = self.supervisor.status()
        checks["effect_worker"] = (
            "DOWN" if supervisor.state is SupervisorState.STOPPED else
            "DEGRADED" if supervisor.state is SupervisorState.DEGRADED else "UP"
        )
        ready = all(value == "UP" for value in checks.values())
        return {
            "status": "READY" if ready else "NOT_READY",
            "checks": checks,
            "custody_model": "NON_CUSTODIAL",
            "providers": ["BANK-KE", "MPESA-KE"],
        }


def compose_deployed_sandbox(
    *, config: DeployedSandboxConfig, key_client: IsolatedKeyServiceClient,
    effect_consumer: ProviderEffectConsumer,
    connection_factory: ConnectionFactory | None = None,
) -> DeployedSandboxRuntime:
    config.validate()
    factory = connection_factory or psycopg_connection_factory(config.database_url)
    database = PostgresDatabase(factory)
    keys = RemoteKeyEncryptionProvider(key_client)
    encryption = EnvelopeEncryptionService(
        keys=keys,
        active_key_ids={
            EncryptionPurpose.ACCOUNT_ENDPOINT: config.account_endpoint_key_id,
            EncryptionPurpose.CONTACT_DESTINATION: config.contact_destination_key_id,
            EncryptionPurpose.PROVIDER_CREDENTIAL: config.provider_credential_key_id,
            EncryptionPurpose.NOTIFICATION_BODY: config.notification_body_key_id,
        },
    )
    secret_store = PostgresEncryptedSecretStore(database)
    account_endpoints = EncryptedAccountEndpointVault(
        encryption=encryption, store=secret_store
    )
    contact_destinations = EncryptedContactBindingVault(
        encryption=encryption, store=secret_store
    )
    provider_credentials = EncryptedProviderCredentialVault(
        encryption=encryption, store=secret_store
    )
    notifications = PostgresSettlementNotificationStore(
        database, body_protector=NotificationBodyProtector(encryption),
        require_encrypted_bodies=True,
    )
    metrics = MetricsRegistry()
    effect_store = PostgresSandboxEffectStore(database)
    effects = SandboxEffectBroker(metrics=metrics, effect_store=effect_store)
    worker = SandboxEffectWorker(
        broker=effects, consumer=effect_consumer, metrics=metrics,
        worker_id=config.worker_id,
    )
    return DeployedSandboxRuntime(
        config=config, database=database,
        migrations=MigrationRunner(
            connection_factory=factory,
            migrations_directory=config.migrations_directory,
        ),
        identity=PostgresIdentityRepository(database),
        contracts=PostgresContractStore(database),
        executions=PostgresExecutionStore(database),
        operations=PostgresOperationsStore(database),
        institution_manifests=PostgresInstitutionManifestStore(database),
        certification_reports=PostgresCertificationReportStore(database),
        certification_runs=PostgresCertificationRunRecorder(database),
        history=PostgresTransactionHistoryStore(database),
        projections=PostgresProviderOutcomeProjectionStore(database),
        callbacks=PostgresCallbackInboxStore(database),
        partners=PostgresPartnerDirectory(database),
        notifications=notifications,
        account_endpoints=account_endpoints,
        contact_destinations=contact_destinations,
        provider_credentials=provider_credentials,
        effects=effects, bank_adapter=SandboxBankAdapter(effects),
        mpesa_adapter=SandboxMpesaAdapter(effects),
        supervisor=WorkerSupervisor(worker), metrics=metrics,
        connection_factory=factory,
    )
