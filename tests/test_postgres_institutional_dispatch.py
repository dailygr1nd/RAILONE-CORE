"""Exercise institutional dispatch using signed domain records and scripted SQL results."""
from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import timedelta
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from railone_authority.models import ReceiverParticipationMode
from railone_authority.service import ExecutionAuthorityService
from railone_identity.models import IdentityStatus
from railone_institutions import CapabilityManifestSigner, InstitutionAdapterRegistry
from railone_institutions.reference import (
    DOMESTIC_BANK_PROFILE, ReferenceInstitutionAdapter, reference_manifest,
)
from railone_institutions.wrapper import CanonicalDispatchWrapper, DispatchWrapperService
from railone_operations.store import InMemoryOperationsStore
from railone_postgres.fencing import EconomicFenceViolation
from railone_sandbox.deployment import DeployedSandboxConfig, compose_deployed_sandbox
from tests.test_deployed_sandbox_composition import NoopConsumer, NoopKeyClient
from tests.test_durable_economic_fencing import FakeDatabase
from tests.test_institution_dispatch_wrapper import sections
from tests import test_provider_operations as provider_tests


KEY_ID = "R1CORE:execution:2026-01"


class PostgresInstitutionalDispatchTests(unittest.TestCase):
    def setUp(self):
        fixture = provider_tests.ProviderOperationsTests(
            "test_preparation_is_idempotent_and_uses_stable_provider_key"
        )
        fixture._create_current_rtt = partial(fixture._create_current_rtt, institutional=True)
        fixture.setUp()
        self.fixture = fixture
        self.at = fixture.now + timedelta(seconds=22)
        self.rtt_id = fixture.rtt_id
        fixture.endpoint_resolver.register(
            institution_id="INST-SOURCE", account_binding_id="acctbind_payer_ops",
            provider_reference="PAYER-TEST-REF",
        )
        fixture.endpoint_resolver.register(
            institution_id="INST-DEST", account_binding_id="acctbind_ben_ops",
            provider_reference="BENEFICIARY-TEST-REF",
        )
        _, self.request = fixture.coordinator.prepare(rtt_id=self.rtt_id, at=self.at)
        utt = fixture.contracts.require_utt(self.request.utt_id).payload
        accepted = fixture.contracts.resolve_idempotency("IDEM-OPS-001", utt["acceptance_request_sha256"])
        self.receiver = ExecutionAuthorityService(fixture.signatures).issue_receiver_participation(
            sender_authority=accepted.sender_authority, receiver_actor_type="PERSON",
            receiver_reference=utt["beneficiary"]["actor_id"],
            participation_mode=ReceiverParticipationMode.ACTIVE_ACCEPTANCE,
            evidence_reference="SYNTHETIC-ACCEPTANCE", signing_key_id=KEY_ID,
            attested_at=fixture.now + timedelta(seconds=11), expires_at=fixture.now + timedelta(minutes=1),
        )
        self.authorities = [
            {"authority_type": kind, "authority_id": envelope.payload[field],
             "signed_envelope": envelope.to_dict()}
            for kind, envelope, field in (
                ("ETK_R", self.receiver, "etk_r_id"),
                ("ETK_S", accepted.sender_authority, "etk_s_id"),
            )
        ]
        signer = CapabilityManifestSigner(fixture.signatures, signing_key_id=KEY_ID)
        profile = replace(
            DOMESTIC_BANK_PROFILE, adapter_id="provider-fast", provider_id="PROVIDER-FAST",
            rails=("MOBILE_MONEY",),
        )
        manifest = reference_manifest(
            profile, source_institution_ids=("INST-SOURCE",),
            destination_institution_ids=("INST-DEST",), now=fixture.now,
        )
        signed_manifest = signer.sign(manifest, issued_at=fixture.now)
        self.manifest_digest = signed_manifest.signature.protected["payload_sha256"]
        self.adapter = ReferenceInstitutionAdapter(manifest)
        self.adapter.submit = Mock(wraps=self.adapter.submit)
        self.registry = InstitutionAdapterRegistry(signer)
        self.registry.register(self.adapter, signed_manifest)
        self.db = FakeDatabase()
        config = DeployedSandboxConfig(
            database_url="postgresql://synthetic",
            migrations_directory=Path(__file__).resolve().parents[1] / "migrations",
            account_endpoint_key_id="account-v1", contact_destination_key_id="contact-v1",
            provider_credential_key_id="credential-v1", notification_body_key_id="notification-v1",
            worker_id="worker-1",
        )
        runtime = compose_deployed_sandbox(
            config=config, key_client=NoopKeyClient(), effect_consumer=NoopConsumer(),
            connection_factory=lambda: None,
        )
        self.operations = InMemoryOperationsStore()
        self.endpoints = Mock(wraps=fixture.endpoint_resolver)
        self.runtime = replace(
            runtime, database=self.db, contracts=fixture.contracts, executions=fixture.executions,
            operations=self.operations, account_endpoints=self.endpoints,
        )
        active = SimpleNamespace(status=IdentityStatus.ACTIVE)
        identities = Mock()
        identities.get_by_continuity_uid.return_value = SimpleNamespace(
            identity=active, active_revision=active,
        )
        manifests = Mock()
        manifests.require.return_value = SimpleNamespace(
            provider_id="PROVIDER-FAST", payload_sha256=self.manifest_digest,
        )
        self.wrappers = Mock()
        replacements = {
            "railone_postgres.dispatch_snapshot.PostgresContractStore": fixture.contracts,
            "railone_postgres.dispatch_snapshot.PostgresExecutionStore": fixture.executions,
            "railone_postgres.dispatch_snapshot.PostgresIdentityRepository": identities,
            "railone_postgres.dispatch_snapshot.PostgresInstitutionManifestStore": manifests,
            "railone_postgres.dispatch_snapshot.PostgresPartnerDirectory": Mock(),
            "railone_sandbox.deployment.PostgresDispatchWrapperStore": self.wrappers,
        }
        for target, value in replacements.items():
            self.enterContext(patch(target, return_value=value))
        from railone_postgres.dispatch_snapshot import PostgresDispatchSnapshotReader

        self.reader = PostgresDispatchSnapshotReader(
            self.db, signatures=fixture.signatures, core_owner_id="R1CORE",
        )
        self.dispatcher = self.runtime.institutional_dispatcher(
            signatures=fixture.signatures, registry=self.registry,
            event_signing_key_id=KEY_ID, wrapper_signing_key_id=KEY_ID,
            trusted_no_effect_signing_keys=frozenset({"synthetic-no-effect-signer"}),
            core_owner_id="R1CORE", require_sender_first=False,
        )

    def provision_wrapper(self, *, request_digest=None):
        self.db._cursor.selected.extend((self.authorities, None))
        expected = self.reader.load(rtt_id=self.rtt_id, at=self.at)
        self.assertEqual(expected.etk_r_digest, self.receiver.protected["payload_sha256"])
        self.assertIsNone(expected.request_sha256)
        expected = replace(expected, request_sha256=request_digest or self.request.request_sha256)
        body = sections()
        for section in body.values():
            for field in section:
                if hasattr(expected, field):
                    section[field] = getattr(expected, field)
        wrapper = CanonicalDispatchWrapper.build(
            issued_at_epoch=int(self.at.timestamp()), expires_at_epoch=int(self.at.timestamp()) + 30,
            **body,
        )
        verifier = DispatchWrapperService(
            self.fixture.signatures, signing_key_id=KEY_ID, expected_core_owner_id="R1CORE",
        )
        self.wrappers.require.return_value = verifier.issue(wrapper, expected=expected, at=self.at)

    def test_dispatch_reserves_and_commits_before_adapter_call_and_blocks_replay(self):
        self.provision_wrapper()
        current = {"rtt_id": self.rtt_id}
        self.db._cursor.selected.extend((
            self.authorities, None, None, None, current,  # snapshot and preflight
            self.authorities, None, None, None, current,  # snapshot and final admission
            {"utt_id": self.request.utt_id}, None, current, None,  # reservation
            {"fence_epoch": 1},  # outcome observation
        ))
        submit = self.adapter.submit

        def check_reservation(instruction):
            self.assertEqual(self.db.commits, 6)
            self.assertIn("INSERT INTO railone.rtt_operational_fences", self.db._cursor.executed[-2][0])
            return submit(instruction)

        self.adapter.submit = check_reservation
        result = self.dispatcher.dispatch(rtt_id=self.rtt_id, at=self.at)
        self.assertEqual(result.state.value, "ACCEPTED")
        self.assertEqual(submit.call_count, 1)
        self.assertFalse(self.db._cursor.selected)

        held = {"state": "HELD", "fence_epoch": 1, "last_release_evidence_id": None}
        self.db._cursor.selected.extend((self.authorities, held, held))
        with self.assertRaises(EconomicFenceViolation):
            self.dispatcher.dispatch(rtt_id=self.rtt_id, at=self.at)
        self.assertEqual(submit.call_count, 1)
        self.assertEqual(self.endpoints.resolve.call_count, 2)

    def test_reservation_race_denies_adapter_call_after_successful_preflight(self):
        self.provision_wrapper()
        current = {"rtt_id": self.rtt_id}
        held = {"state": "HELD", "fence_epoch": 1, "last_release_evidence_id": None}
        self.db._cursor.selected.extend((
            self.authorities, None, None, None, current,
            self.authorities, None, None, None, current,
            {"utt_id": self.request.utt_id}, None, current, held,
        ))
        with self.assertRaises(EconomicFenceViolation):
            self.dispatcher.dispatch(rtt_id=self.rtt_id, at=self.at)
        self.assertEqual(self.db.rollbacks, 1)
        self.assertFalse(self.adapter.submit.called)
        self.assertEqual(self.operations.require_submission(self.rtt_id).state.value, "PREPARED")

    def test_digest_mismatch_does_not_persist_submission_or_reserve(self):
        self.provision_wrapper(request_digest="1" * 64)
        self.db._cursor.selected.extend((
            self.authorities, None, None, None, {"rtt_id": self.rtt_id},
        ))
        with self.assertRaisesRegex(PermissionError, "resolved provider request"):
            self.dispatcher.dispatch(rtt_id=self.rtt_id, at=self.at)
        with self.assertRaises(LookupError):
            self.operations.require_submission(self.rtt_id)
        self.assertFalse(self.adapter.submit.called)
        self.assertFalse(any("FOR UPDATE" in query for query, _ in self.db._cursor.executed))

    def test_missing_receiver_authority_stops_before_wrapper_or_vault(self):
        self.db._cursor.selected.append(self.authorities[1:])
        with self.assertRaisesRegex(PermissionError, "receiver and sender authority"):
            self.dispatcher.dispatch(rtt_id=self.rtt_id, at=self.at)
        self.assertFalse(self.wrappers.require.called)
        self.assertFalse(self.endpoints.resolve.called)
        self.assertFalse(self.adapter.submit.called)
