"""Synthetic provisioning and full PostgreSQL institutional dispatch exercise."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from railone_contracts import AccountRole
from railone_identity.models import (
    IdentityBundle, IdentityGenesis, IdentityObject, IdentityRevision, IdentityStatus, TrustTier,
)
from railone_institutions import CapabilityManifestSigner, InstitutionAdapterRegistry
from railone_institutions.reference import DOMESTIC_BANK_PROFILE, ReferenceInstitutionAdapter, reference_manifest
from railone_institutions.wrapper import CanonicalDispatchWrapper, DispatchWrapperService
from railone_postgres import (
    PostgresContractStore, PostgresExecutionStore, PostgresOperationsStore,
    PostgresIdentityRepository, PostgresPartnerDirectory, PostgresInstitutionManifestStore,
    PostgresEncryptedSecretStore, PostgresDispatchWrapperStore, EconomicFenceViolation,
)
from railone_postgres.dispatch_snapshot import PostgresDispatchSnapshotReader
from railone_partners import PartnerInstitution, AccountBinding
from railone_security import EncryptedAccountEndpointVault
from railone_sandbox.deployment import DeployedSandboxConfig, compose_deployed_sandbox
from tests import test_provider_operations as fixtures
from tests.test_deployed_sandbox_composition import NoopKeyClient, NoopConsumer
from tests.test_envelope_encryption import encryption_fixture
from tests.test_institution_dispatch_wrapper import sections


class SimulatedWorkerCrash(BaseException):
    """Test-only process interruption after the committed reservation."""


def _accept_via_http(test, database, fixture, *, signed_quote, sender, receiver, origin, emit):
    """Exercise real FastAPI HTTP routes, persisted API audit, and UTT creation.

    This uses TestClient (in-process ASGI), not an externally deployed server.
    All keys, identities and bank endpoints are synthetic; never real funds.
    """
    from types import SimpleNamespace

    from fastapi.testclient import TestClient
    from railone_api import AccessTokenService, ActorScopes, PrincipalType
    from railone_api.http import create_app
    from railone_crypto.key_provider import KeyPurpose
    from railone_postgres import PostgresTokenRevocationStore
    from railone_sandbox.deployment import DeployedSandboxConfig, compose_deployed_sandbox

    now = fixture.now
    for key_id, owner, purpose in (
        ("E2E-HTTP-TOKEN", "R1AUTH", KeyPurpose.ACCESS_TOKEN_SIGNING),
        ("E2E-HTTP-AUDIT", "RAILONE", KeyPurpose.API_AUDIT_SIGNING),
    ):
        fixture.keys.generate(
            key_id=key_id, owner_id=owner, purpose=purpose,
            not_before=now-timedelta(days=1), not_after=now+timedelta(days=2),
        )
    tokens = AccessTokenService(
        keys=fixture.keys, issuer="railone-v017-synthetic",
        revocations=PostgresTokenRevocationStore(database),
    )
    config = DeployedSandboxConfig(
        database_url="postgresql://synthetic",
        migrations_directory=Path(__file__).resolve().parents[1]/"migrations",
        account_endpoint_key_id="synthetic-endpoint", contact_destination_key_id="synthetic-contact",
        provider_credential_key_id="synthetic-credential",
        notification_body_key_id="synthetic-notification", worker_id="synthetic-api",
    )
    runtime = compose_deployed_sandbox(
        config=config, key_client=NoopKeyClient(), effect_consumer=NoopConsumer(),
        connection_factory=test.factory,
    )
    facade = runtime.authenticated_p2p_facade(
        signatures=fixture.signatures, access_tokens=tokens,
        utt_signing_key_id="R1CORE:execution:2026-01",
        authority_signing_key_id="R1CORE:execution:2026-01",
        api_audit_signing_key_id="E2E-HTTP-AUDIT",
    )
    client = TestClient(create_app(facade=facade))
    payer = signed_quote.payload["payer"]["actor_id"]
    beneficiary = signed_quote.payload["beneficiary"]["actor_id"]

    def token(uid, *, partner=False):
        return tokens.issue(
            principal_id=f"E2E-{'PARTNER' if partner else 'ACTOR'}-{uid}",
            principal_type=PrincipalType.PARTNER_SERVICE if partner else PrincipalType.HUMAN,
            scopes=ActorScopes(partner_ids=(uid,)) if partner
                   else ActorScopes(continuity_uid=uid),
            key_id="E2E-HTTP-TOKEN", at=now,
        )

    payer_token = token(payer)
    receiver_token = token(beneficiary)
    if fixture.delegated:
        from railone_authority.bilateral import BilateralAuthorityService
        from railone_authority.mandates import grant
        terms = signed_quote.payload
        endpoint = terms["beneficiary"]["endpoint"]
        institution = endpoint["institution_id"]
        def new_grant():
            return grant(fixture.signatures, beneficiary=beneficiary, institution=institution,
                       account_binding_id=endpoint["account_binding_id"], currency=terms["currency_to"],
                       max_receive_minor=terms["receive_amount_minor"], issued_at=now,
                       expires_at=now + timedelta(minutes=4), signing_key_id="fixture-receiver-v3")
        fixture.keys.generate(key_id="fixture-delegate", owner_id=institution,
                              purpose=KeyPurpose.EXECUTION_SIGNING,
                              not_before=now-timedelta(days=1), not_after=now+timedelta(days=1))
        def sign_acceptance(mandate):
            return BilateralAuthorityService(fixture.signatures).issue_receiver_acceptance(
                signed_quote=signed_quote, sender=sender, mandate=mandate, signing_key_id="fixture-delegate",
                accepted_at=now+timedelta(seconds=7), expires_at=now+timedelta(minutes=2))
        mandate = new_grant()
        receiver = sign_acceptance(mandate)
        receiver_token = token(institution, partner=True)
    hostile_token = token("AGG-COMPROMISED", partner=True)
    body = {
        "signed_quote": signed_quote.to_dict(),
        "sender_authority": sender.to_dict(),
        "receiver_authority": receiver.to_dict(),
        "origin_intent_id": origin.origin_intent_id,
    }

    def post(path, access, *, payload=None, idem=None):
        headers = {"Authorization": "Bearer " + access}
        if idem:
            headers["Idempotency-Key"] = idem
        return client.post(
            "/v1/bilateral/p2p/" + path, headers=headers,
            json=body if payload is None else payload,
        )

    response = post("etk-s/verify", payer_token)
    test.assertEqual(response.status_code, 200, response.text)
    test.assertEqual(response.json()["status"], "ETK_S_VERIFIED")
    emit("Authenticated sender ETK-S verified over HTTP")
    response = post("etk-r/verify", receiver_token)
    test.assertEqual(response.status_code, 200, response.text)
    test.assertEqual(response.json()["status"], "ETK_R_VERIFIED")
    emit("Authenticated receiver ETK-R verified against the exact ETK-S")

    # A compromised partner with valid credentials must not claim the sender's
    # human identity, even when supplied with both otherwise valid ETKs.
    denied = post("utts", hostile_token, idem="IDEM-E2E-HOSTILE")
    test.assertEqual(denied.status_code, 403, denied.text)
    # A compromised endpoint may tamper with the signed request; signature
    # verification must reject it rather than creating a UTT.
    tampered = {**body, "signed_quote": signed_quote.to_dict()}
    tampered["signed_quote"]["payload"]["amount_minor"] += 1
    denied = post("utts", payer_token, payload=tampered, idem="IDEM-E2E-TAMPER")
    test.assertEqual(denied.status_code, 403, denied.text)
    with database.transaction() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS n FROM railone.accepted_utts")
        test.assertEqual(cursor.fetchone()["n"], 0)
    emit("Compromised partner impersonation and amount tampering denied before UTT")

    if fixture.delegated:
        denied = post("etk-r/verify", hostile_token)
        test.assertEqual(denied.status_code, 403, denied.text)
        denied = post("utts", payer_token, idem="IDEM-OPS-001")
        test.assertEqual(denied.status_code, 403, denied.text)
        # Establish an actual row-lock wait before allowing revocation to commit.
        from concurrent.futures import ThreadPoolExecutor
        from time import monotonic, sleep
        revoked = new_grant()
        fixture.contracts.register_receiving_mandate(revoked, signatures=fixture.signatures)
        revoked_body = {**body, "receiver_authority": sign_acceptance(revoked).to_dict()}
        with ThreadPoolExecutor(max_workers=1) as pool, test.factory() as locker:
            locker.execute("UPDATE railone.receiving_mandates SET revoked_at=clock_timestamp() "
                           "WHERE mandate_id=%s", (revoked.payload["mandate_id"],))
            pending = pool.submit(post, "utts", payer_token, payload=revoked_body, idem="IDEM-OPS-001")
            deadline = monotonic() + 5
            while monotonic() < deadline:
                if locker.execute("SELECT EXISTS (SELECT FROM pg_stat_activity WHERE "
                                  "pg_backend_pid() = ANY(pg_blocking_pids(pid))) AS blocked").fetchone()["blocked"]:
                    break
                locker.execute("SELECT pg_stat_clear_snapshot()")
                sleep(0.02)
            else:
                test.fail("acceptance did not block on the revocation")
            locker.commit()
            denied = pending.result(timeout=5)
            test.assertEqual(denied.status_code, 403, denied.text)
        with database.transaction() as connection:
            for table in ("accepted_utts", "execution_authorities", "acceptance_idempotency"):
                test.assertEqual(connection.execute(f"SELECT count(*) AS n FROM railone.{table}").fetchone()["n"], 0)
        fixture.contracts.register_receiving_mandate(mandate, signatures=fixture.signatures)
    response = post("utts", payer_token, idem="IDEM-OPS-001")
    test.assertEqual(response.status_code, 200, response.text)
    utt = response.json()
    test.assertEqual(utt["authority_version"], 4)
    test.assertFalse(utt["replayed"])
    with database.transaction() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS n FROM railone.accepted_utts")
        test.assertEqual(cursor.fetchone()["n"], 1)
    emit("Immutable bilateral UTT accepted by authenticated HTTP and persisted to PostgreSQL")
    if fixture.delegated:
        fixture.contracts.revoke_receiving_mandate(mandate.payload["mandate_id"])
    replay = post("utts", payer_token, idem="IDEM-OPS-001")
    test.assertEqual(replay.status_code, 200, replay.text)
    test.assertTrue(replay.json()["replayed"])
    test.assertEqual(replay.json()["utt_id"], utt["utt_id"])
    emit("Repeated HTTP acceptance returned the same UTT without duplication")
    return SimpleNamespace(utt_id=utt["utt_id"])


def exercise_institutional_dispatch(
    test, database, *, scenario="accepted", report=None, http_bilateral=False, delegated=False, reconcile_no_effect=False, check_settlement=False,
):
    if scenario not in {"accepted", "timeout", "crash"}:
        raise ValueError("unsupported synthetic scenario")
    emit = report or (lambda message: None)
    fixture = fixtures.ProviderOperationsTests("test_preparation_is_idempotent_and_uses_stable_provider_key")
    _, _, encryption = encryption_fixture()
    vault = EncryptedAccountEndpointVault(
        encryption=encryption, store=PostgresEncryptedSecretStore(database),
    )

    def create():
        fixture.contracts = PostgresContractStore(database)
        fixture.executions = PostgresExecutionStore(database)
        fixture.operations = PostgresOperationsStore(database)
        fixture.endpoint_resolver = vault
        return fixtures.ProviderOperationsTests._create_current_rtt(
            fixture, institutional=True, sender_first=True,
        )

    fixture._create_current_rtt = create
    fixture.delegated = delegated
    fixture.core_owner_id = "RAILONE"
    if http_bilateral:
        # The HTTP facade validates against the wall clock; unlike historical
        # in-process fixtures, this scenario uses fresh short-lived signatures.
        # Manifest signatures encode iat as integral Unix seconds. Use the same
        # precision for the synthetic manifest's issued_at, otherwise the
        # verifier sees a sub-second "issued before valid" mismatch.
        fixture.sandbox_now = (datetime.now(timezone.utc) - timedelta(seconds=10)).replace(
            microsecond=0,
        )
        fixture.external_bilateral_acceptance = lambda **kwargs: _accept_via_http(
            test, database, fixture, emit=emit, **kwargs,
        )
    fixture.setUp()
    at = fixture.now + timedelta(seconds=22)
    attempt = fixture.executions.require_attempt(fixture.rtt_id)
    utt = fixture.contracts.require_utt(attempt.utt_id).payload
    emit(f"Accepted synthetic P2P instruction {attempt.utt_id}")
    # This synthetic fixture uses KES, with two decimal places.
    for label, field, currency in (
        ("Instructed source amount", "amount_minor", utt["currency_from"]),
        ("Expected recipient amount", "receive_amount_minor", utt["currency_to"]),
        ("Customer fee", "total_fee_minor", utt["currency_from"]),
    ):
        minor = utt[field]
        amount = f"{minor // 100:,}.{minor % 100:02d}" if currency == "KES" else f"{minor} minor units"
        emit(f"{label} {currency} {amount}")
    emit("Amounts describe the synthetic instruction; settlement confirmation is pending")
    emit(f"Selected route {attempt.route_id}; created attempt {fixture.rtt_id}")
    identities = PostgresIdentityRepository(database)
    partners = PostgresPartnerDirectory(database)
    for number, actor in enumerate((utt["payer"], utt["beneficiary"]), 1):
        uid = actor["actor_id"]
        prefix = f"LIVE-DISPATCH-{number}"
        identities.save(IdentityBundle(
            IdentityGenesis(prefix+"-GEN", uid, "synthetic-continuity",
                            str(number)*64, "SYNTHETIC-KYC", prefix+"-VERIFY",
                            str(number)*64, prefix+"-ATTEST", fixture.now),
            IdentityObject(prefix+"-OBJ", prefix+"-RID", uid, prefix+"-GEN",
                           prefix+"-REV", "EA", IdentityStatus.ACTIVE, fixture.now),
            IdentityRevision(prefix+"-REV", prefix+"-OBJ", uid, 1, TrustTier.T2,
                             IdentityStatus.ACTIVE, "SYNTHETIC_TEST", prefix+"-ATTEST",
                             fixture.now),
        ))
        endpoint = actor["endpoint"]
        role = AccountRole(endpoint["role"])
        partners.add_institution(PartnerInstitution(
            endpoint["institution_id"], endpoint["institution_display_name"],
            ("KE",), ("KES",), (role,),
        ), at=fixture.now)
        from railone_contracts import AccountType
        partners.add_binding(AccountBinding(
            endpoint["account_binding_id"], uid, endpoint["institution_id"],
            role, AccountType(endpoint["account_type"]), "KES",
            endpoint["display_hint"], endpoint["contact_binding_id"],
            endpoint["attestation_reference"],
        ), at=fixture.now)
        vault.register(
            institution_id=endpoint["institution_id"],
            account_binding_id=endpoint["account_binding_id"],
            provider_reference=prefix+"-SYNTHETIC-ACCOUNT",
        )

    accepted = fixture.contracts.resolve_idempotency("IDEM-OPS-001", utt["acceptance_request_sha256"])
    key = "R1CORE:execution:2026-01"
    # Receiver-first or post-UTT synthetic ETK-R insertion would bypass
    # the bilateral lock. Verify that both v3 authorities were persisted
    # atomically before creating the ExecutionPlan or RTT.
    sender, receiver = fixture.contracts.require_bilateral_authorities(attempt.utt_id)
    test.assertEqual(utt["authority_version"], 4)
    test.assertEqual(receiver.payload["etk_s_digest"], sender.protected["payload_sha256"])
    test.assertEqual(utt["etk_r_digest"], receiver.protected["payload_sha256"])

    signer = CapabilityManifestSigner(fixture.signatures, signing_key_id=key)
    profile = replace(DOMESTIC_BANK_PROFILE, adapter_id="provider-fast",
                      provider_id="PROVIDER-FAST", rails=("MOBILE_MONEY",))
    manifest = reference_manifest(profile, source_institution_ids=("INST-SOURCE",),
                                  destination_institution_ids=("INST-DEST",), now=fixture.now)
    signed_manifest = signer.sign(manifest, issued_at=fixture.now)
    PostgresInstitutionManifestStore(database).put(signed_manifest)
    observed = []

    class ObservedAdapter(ReferenceInstitutionAdapter):
        def submit(self, instruction):
            # A separate connection must see the committed hold before submission.
            with database.transaction() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT state,current_rtt_id FROM railone.utt_economic_fences WHERE utt_id=%s",
                    (instruction.utt_id,),
                )
                row = cursor.fetchone()
            observed.append((row["state"], row["current_rtt_id"]))
            if scenario == "timeout":
                raise TimeoutError("synthetic provider timeout")
            if scenario == "crash":
                raise SimulatedWorkerCrash()
            return super().submit(instruction)

    registry = InstitutionAdapterRegistry(signer)
    registry.register(ObservedAdapter(manifest), signed_manifest)

    # Trusted synthetic provisioning prepares the digest and issues the stored wrapper.
    _, request = fixture.coordinator.prepare(rtt_id=fixture.rtt_id, at=at)
    expected = PostgresDispatchSnapshotReader(
        database, signatures=fixture.signatures, core_owner_id="RAILONE",
        require_sender_first=True,
    ).load(rtt_id=fixture.rtt_id, at=at)
    expected = replace(expected, request_sha256=request.request_sha256)
    body = sections()
    for section in body.values():
        for field in section:
            if hasattr(expected, field):
                section[field] = getattr(expected, field)
    verifier = DispatchWrapperService(fixture.signatures, signing_key_id=key,
                                      expected_core_owner_id="RAILONE")
    wrapper = CanonicalDispatchWrapper.build(
        issued_at_epoch=int(at.timestamp()), expires_at_epoch=int(at.timestamp())+30, **body,
    )
    PostgresDispatchWrapperStore(database, verifier).put(
        verifier.issue(wrapper, expected=expected, at=at), expected=expected, at=at,
    )
    emit("Persisted bilateral authorities, encrypted endpoints, and signed dispatch wrapper")
    config = DeployedSandboxConfig(
        database_url="postgresql://synthetic",
        migrations_directory=Path(__file__).resolve().parents[1]/"migrations",
        account_endpoint_key_id="test-account", contact_destination_key_id="test-contact",
        provider_credential_key_id="test-provider", notification_body_key_id="test-notification",
        worker_id="live-test",
    )
    runtime = compose_deployed_sandbox(
        config=config, key_client=NoopKeyClient(), effect_consumer=NoopConsumer(),
        connection_factory=test.factory,
    )
    runtime = replace(runtime, account_endpoints=vault)
    dispatcher = runtime.institutional_dispatcher(
        signatures=fixture.signatures, registry=registry, event_signing_key_id=key,
        wrapper_signing_key_id=key, trusted_no_effect_signing_keys=frozenset({"synthetic-unused"}),
        core_owner_id="RAILONE",
    )
    if scenario == "crash":
        with test.assertRaises(SimulatedWorkerCrash):
            dispatcher.dispatch(rtt_id=fixture.rtt_id, at=at)
        emit("Simulated worker interruption after reservation")
    else:
        result = dispatcher.dispatch(rtt_id=fixture.rtt_id, at=at)
        expected_state = "ACCEPTED" if scenario == "accepted" else "UNKNOWN"
        test.assertEqual(result.state.value, expected_state)
        emit(f"Provider submission state {expected_state}")
    test.assertEqual(observed, [("HELD", fixture.rtt_id)])
    emit("Verified committed economic hold through a separate database connection")
    # Recompose to prove replay protection survives coordinator recreation.
    restarted = runtime.institutional_dispatcher(
        signatures=fixture.signatures, registry=registry, event_signing_key_id=key,
        wrapper_signing_key_id=key, trusted_no_effect_signing_keys=frozenset({"synthetic-unused"}),
        core_owner_id="RAILONE",
    )
    with test.assertRaises(EconomicFenceViolation):
        restarted.dispatch(rtt_id=fixture.rtt_id, at=at)
    test.assertEqual(len(observed), 1)
    emit("Recreated dispatcher; duplicate attempt blocked; adapter invoked once")
    with database.transaction() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT state FROM railone.rtt_operational_fences WHERE rtt_id=%s",
                       (fixture.rtt_id,))
        expected_fence = {
            "accepted": "ACCEPTED_FOR_PROCESSING", "timeout": "UNKNOWN", "crash": "RESERVED",
        }[scenario]
        test.assertEqual(cursor.fetchone()["state"], expected_fence)
        cursor.execute("SELECT state FROM railone.utt_economic_fences WHERE utt_id=%s",
                       (attempt.utt_id,))
        test.assertEqual(cursor.fetchone()["state"], "HELD")
        cursor.execute("SELECT count(*) AS total FROM railone.settlement_evidence WHERE utt_id=%s",
                       (attempt.utt_id,))
        test.assertEqual(cursor.fetchone()["total"], 0)
    emit(f"RTT state {expected_fence}; economic hold HELD; settlement evidence count 0")
    if check_settlement:
        from railone_crypto import KeyPurpose
        from railone_crypto.signature_service import ArtifactType
        from railone_notifications import SettlementEvidenceRecord
        from railone_postgres import PostgresSettlementNotificationStore

        fixture.keys.generate(key_id="test-settlement", owner_id="RECONCILIATION",
                              purpose=KeyPurpose.SETTLEMENT_SIGNING,
                              not_before=at-timedelta(days=1), not_after=at+timedelta(days=1))
        with database.transaction() as connection:
            reference = connection.execute("SELECT external_reference FROM railone.provider_submissions "
                                           "WHERE rtt_id=%s", (fixture.rtt_id,)).fetchone()["external_reference"]
        def record(reference):
            fields = dict(evidence_id="SET-SANDBOX", utt_id=attempt.utt_id, provider_id="PROVIDER-FAST",
                          provider_transaction_id=reference, callback_event_id="CALLBACK-SANDBOX")
            signed = fixture.signatures.sign_artifact(
                artifact_type=ArtifactType.SETTLEMENT_EVIDENCE, key_id="test-settlement",
                payload={**fields, "rtt_id": fixture.rtt_id}, issued_at=at)
            return SettlementEvidenceRecord(**fields, signed_evidence=signed, settled_at=at)
        store = PostgresSettlementNotificationStore(database)
        with test.assertRaises(EconomicFenceViolation):
            store.commit_settlement(record("UNRELATED-REFERENCE"), ())
        if scenario == "accepted":
            test.assertTrue(reference)
            evidence = record(reference)
            test.assertFalse(store.commit_settlement(evidence, ())[2])
            test.assertTrue(store.commit_settlement(evidence, ())[2])
        with database.transaction() as connection:
            settled = connection.execute("SELECT count(*) AS n FROM railone.fence_event_integrity "
                                         "WHERE utt_id=%s AND event_type='SETTLED' AND valid",
                                         (attempt.utt_id,)).fetchone()["n"]
            test.assertEqual(settled, int(scenario == "accepted"))
            row = connection.execute("SELECT state FROM railone.utt_economic_fences WHERE utt_id=%s",
                                     (attempt.utt_id,)).fetchone()
            test.assertEqual(row["state"], "FINALIZED" if scenario == "accepted" else "HELD")
            count = connection.execute("SELECT count(*) AS n FROM railone.settlement_evidence "
                                       "WHERE utt_id=%s", (attempt.utt_id,)).fetchone()["n"]
            test.assertEqual(count, settled)
    if reconcile_no_effect:
        test.assertEqual(scenario, "timeout")
        from hashlib import sha256
        from railone_crypto import KeyPurpose
        from railone_crypto.signature_service import ArtifactType
        from railone_postgres.fencing import PostgresEconomicEffectFence

        signer_id = "sandbox-reconciliation"
        fixture.keys.generate(key_id=signer_id, owner_id="RECONCILIATION",
                              purpose=KeyPurpose.SETTLEMENT_SIGNING,
                              not_before=at-timedelta(days=1), not_after=at+timedelta(days=1))
        fence = PostgresEconomicEffectFence(database, signatures=fixture.signatures,
                                           trusted_no_effect_signing_keys=frozenset({signer_id}))
        checked = at + timedelta(seconds=5)
        def proof(observed):
            return fixture.signatures.sign_artifact(
                artifact_type=ArtifactType.NO_EFFECT_EVIDENCE, key_id=signer_id, issued_at=checked,
                payload=dict(evidence_id="EVID-RECONCILED", utt_id=attempt.utt_id, rtt_id=fixture.rtt_id,
                             provider_id="PROVIDER-FAST", finding="NO_ECONOMIC_EFFECT",
                             source_evidence_digest=sha256(b"synthetic provider reconciliation record").hexdigest(),
                             observed_at_epoch=int(observed.timestamp())))
        with test.assertRaises(EconomicFenceViolation):
            fence.release_verified_no_effect(evidence=proof(at-timedelta(seconds=1)), at=checked)
        evidence = proof(checked)
        epoch = fence.release_verified_no_effect(evidence=evidence, at=checked)
        test.assertEqual(epoch, 2)
        with test.assertRaises(EconomicFenceViolation):
            fence.release_verified_no_effect(evidence=evidence, at=checked)
        with database.transaction() as connection:
            row = connection.execute("SELECT state,fence_epoch FROM railone.utt_economic_fences "
                                     "WHERE utt_id=%s", (attempt.utt_id,)).fetchone()
            test.assertEqual(row, {"state": "OPEN", "fence_epoch": 2})
            row = connection.execute("SELECT state FROM railone.rtt_operational_fences WHERE rtt_id=%s",
                                     (fixture.rtt_id,)).fetchone()
            test.assertEqual(row["state"], "RELEASED_NO_EFFECT")
            row = connection.execute("SELECT count(*) AS n FROM railone.economic_fence_events "
                                     "WHERE utt_id=%s AND event_type='VERIFIED_NO_EFFECT'",
                                     (attempt.utt_id,)).fetchone()
            test.assertEqual(row["n"], 1)
        with database.transaction() as connection:
            chain = connection.execute(
                "SELECT event_type,valid FROM railone.fence_event_integrity "
                "WHERE utt_id=%s ORDER BY chain_position", (attempt.utt_id,)
            ).fetchall()
            test.assertEqual([r["event_type"] for r in chain],
                             ["RESERVED", "PROVIDER_UNKNOWN", "VERIFIED_NO_EFFECT"])
            test.assertTrue(all(r["valid"] for r in chain))
            # Rehash a changed copy without mutating the append-only stream.
            matches = connection.execute(
                """SELECT event_hash = railone.fence_event_hash(jsonb_populate_record(
                       NULL::railone.economic_fence_events,
                       to_jsonb(e) || jsonb_build_object('evidence_id','EVID-CHANGED'))) AS matches
                   FROM railone.economic_fence_events e WHERE utt_id=%s AND chain_position=3""",
                (attempt.utt_id,)
            ).fetchone()
            test.assertFalse(matches["matches"])
        emit("Verified three linked economic fence records for this UTT")
        test.assertEqual(len(observed), 1)
        emit("Signed no-effect reconciliation released the hold at epoch 2; duplicate proof denied")
    if http_bilateral:
        with database.transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT status_code, outcome FROM railone.api_request_audit "
                "WHERE route_template LIKE '/v1/bilateral/p2p/%'"
            )
            events = cursor.fetchall()
        expected_denials = 5 if delegated else 2
        test.assertEqual(len(events), 4 + expected_denials)
        test.assertEqual(sum(event["status_code"] == 403 for event in events), expected_denials)
        test.assertEqual(sum(event["status_code"] == 200 for event in events), 4)
        emit(f"Authenticated API audit: 4 allowed, {expected_denials} denied; all durably recorded")
