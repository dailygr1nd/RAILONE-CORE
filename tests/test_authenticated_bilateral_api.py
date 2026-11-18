"""External, authenticated sender-first bilateral API sandbox conformance."""
from __future__ import annotations

from tests.support import beneficiary_evidence
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from railone_api import (
    AccessTokenService, ActorScopes, AuthenticatedRequestGuard,
    BilateralP2PApi, InMemoryApiAuditStore, InMemoryRateLimitStore,
    PrincipalType, RailOneApiFacade,
)
from railone_crypto.key_provider import KeyPurpose
from railone_crypto.signature_service import ArtifactType, SignatureService
from railone_history import InMemoryTransactionHistoryStore, TransactionHistoryService
from railone_projection import InMemoryProviderOutcomeProjectionStore
import tests.test_compromised_institution_harness as synthetic

try:
    from fastapi.testclient import TestClient
except ImportError:
    TestClient = None


@unittest.skipIf(TestClient is None, "optional FastAPI API dependencies required")
class AuthenticatedBilateralApiTests(unittest.TestCase):
    SENDER = "CUID-" + "A" * 32
    RECEIVER = "CUID-" + "B" * 32
    OUTSIDER = "CUID-" + "C" * 32

    def setUp(self):
        from railone_api.http import create_app
        self.create_app = create_app
        now = datetime.now(timezone.utc) - timedelta(seconds=15)
        self.fx = synthetic.CompromisedInstitutionHarnessTests(
            "test_01_sender_first_bilateral_to_signed_utt_and_rtt"
        )
        self.fx.initialize_at(now)
        self.fx.terms = replace(
            self.fx.terms,
            payer=replace(self.fx.terms.payer, actor_id=self.SENDER),
            beneficiary=replace(self.fx.terms.beneficiary, actor_id=self.RECEIVER),
        )
        self.fx.directory._bindings["BIND-TZ"] = replace(
            self.fx.directory._bindings["BIND-TZ"], actor_id=self.SENDER,
        )
        self.fx.directory._bindings["BIND-KE"] = replace(
            self.fx.directory._bindings["BIND-KE"], actor_id=self.RECEIVER,
        )
        self.fx.quote = self.fx.make_quote()
        for owner, key_id, purpose in (
            (self.SENDER, "api-sender", KeyPurpose.EXECUTION_SIGNING),
            (self.RECEIVER, "api-receiver", KeyPurpose.EXECUTION_SIGNING),
            ("R1AUTH", "api-token", KeyPurpose.ACCESS_TOKEN_SIGNING),
            ("R1CORE", "api-audit", KeyPurpose.API_AUDIT_SIGNING),
        ):
            self.fx.keys.generate(
                key_id=key_id, owner_id=owner, purpose=purpose,
                not_before=now-timedelta(days=1),
                not_after=now+timedelta(days=2),
            )
        self.sender = self.fx.sender(signing_key_id="api-sender", expires=45)
        self.receiver = self.fx.receiver(self.sender, signing_key_id="api-receiver", expires=40)
        self.signatures = SignatureService(self.fx.keys)
        self.tokens = AccessTokenService(keys=self.fx.keys, issuer="railone-bilateral-test")
        self.sender_token = self._token(self.SENDER)
        self.receiver_token = self._token(self.RECEIVER)
        self.outsider_token = self._token(self.OUTSIDER)
        self.audits = InMemoryApiAuditStore()
        self.guard = AuthenticatedRequestGuard(
            tokens=self.tokens, rate_limits=InMemoryRateLimitStore(),
            audits=self.audits, signatures=self.signatures,
            audit_signing_key_id="api-audit",
        )
        self.facade = RailOneApiFacade(
            guard=self.guard,
            history=TransactionHistoryService(InMemoryTransactionHistoryStore()),
            outcomes=InMemoryProviderOutcomeProjectionStore(),
            bilateral_p2p=BilateralP2PApi(
                bilateral=self.fx.bilateral, acceptance=self.fx.accept,
            ),
        )
        self.client = TestClient(create_app(facade=self.facade))

    def _token(self, uid):
        return self.tokens.issue(
            principal_id="API-" + uid, principal_type=PrincipalType.HUMAN,
            scopes=ActorScopes(continuity_uid=uid),
            key_id="api-token", at=self.fx.now,
        )

    def _headers(self, token, *, key=None):
        headers = {"Authorization": "Bearer " + token}
        if key is not None:
            headers["Idempotency-Key"] = key
        return headers

    def _body(self):
        return {
            "signed_quote": self.fx.quote.to_dict(),
            "sender_authority": self.sender.to_dict(),
            "receiver_authority": self.receiver.to_dict(),
            "origin_intent_id": "MOBILE-P2P-001",
        }

    def _post(self, endpoint, token, body=None, *, key=None):
        return self.client.post(
            "/v1/bilateral/p2p/" + endpoint,
            json=self._body() if body is None else body,
            headers=self._headers(token, key=key),
        )

    def test_sender_receiver_then_utt_and_idempotent_replay(self):
        s = self._post("etk-s/verify", self.sender_token)
        self.assertEqual(s.status_code, 200, s.text)
        self.assertEqual(s.json()["status"], "ETK_S_VERIFIED")
        self.assertFalse(s.json()["persisted"])
        r = self._post("etk-r/verify", self.receiver_token)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["status"], "ETK_R_VERIFIED")
        self.assertFalse(r.json()["persisted"])
        key = "IDEM-P2P-API-001"
        u = self._post("utts", self.sender_token, key=key)
        self.assertEqual(u.status_code, 200, u.text)
        self.assertEqual(u.json()["authority_version"], 4)
        self.assertFalse(u.json()["replayed"])
        replay = self._post("utts", self.sender_token, key=key)
        self.assertEqual(replay.status_code, 200, replay.text)
        self.assertTrue(replay.json()["replayed"])
        self.assertEqual(replay.json()["utt_id"], u.json()["utt_id"])
        self.assertEqual(len(self.fx.contracts._utts), 1)
        stored_s, stored_r = self.fx.contracts.require_bilateral_authorities(u.json()["utt_id"])
        self.assertEqual(stored_r.payload["etk_s_digest"], stored_s.protected["payload_sha256"])
        # Prove the API-created persisted UTT enters the original execution
        # planning + RTT pipeline without bypassing bilateral verification.
        plan_at = datetime.now(timezone.utc) + timedelta(seconds=1)
        plan = self.fx.plan.build_plan(
            utt_id=u.json()["utt_id"], candidates=(self.fx.route(),),
            at=plan_at,
        )
        attempt = self.fx.attempt.start_next(
            utt_id=u.json()["utt_id"], at=plan_at + timedelta(seconds=1),
        )
        self.assertEqual(attempt.plan_id, plan.plan_id)
        self.assertTrue(all(self.signatures.verify_artifact(
            a.signed_audit, expected_artifact_type=ArtifactType.API_REQUEST_AUDIT,
        ).valid for a in self.audits.audits()))

    def test_repeated_request_id_keeps_distinct_signed_audit_records(self):
        headers = self._headers(self.sender_token)
        headers["X-Request-ID"] = "REQ-REUSED-CORRELATION"
        for _ in range(2):
            response = self.client.post(
                "/v1/bilateral/p2p/etk-s/verify", json=self._body(), headers=headers,
            )
            self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(self.audits.audits()), 2)
        self.assertNotEqual(self.audits.audits()[0].audit_id, self.audits.audits()[1].audit_id)

    def test_malformed_artifact_is_denied_not_an_internal_error(self):
        body = self._body()
        body["signed_quote"]["payload"] = {"payer": {"actor_id": self.SENDER}}
        response = self._post("etk-s/verify", self.sender_token, body)
        self.assertEqual(response.status_code, 403, response.text)

    def test_authentication_must_precede_endpoint_processing(self):
        res = self.client.post("/v1/bilateral/p2p/etk-s/verify", json=self._body())
        self.assertEqual(res.status_code, 401)
        self.assertEqual(self.audits.audits()[-1].principal_id, "UNAUTHENTICATED")

    def test_institution_service_cannot_impersonate_human_scope(self):
        token = self.tokens.issue(
            principal_id="AGGREGATOR-001", principal_type=PrincipalType.PARTNER_SERVICE,
            scopes=ActorScopes(continuity_uid=self.SENDER, partner_ids=("AGGREGATOR-001",)),
            key_id="api-token", at=self.fx.now,
        )
        self.assertEqual(self._post("etk-s/verify", token).status_code, 403)

    def test_sender_token_cannot_claim_receiver_or_vice_versa(self):
        self.assertEqual(self._post("etk-s/verify", self.receiver_token).status_code, 403)
        self.assertEqual(self._post("etk-r/verify", self.sender_token).status_code, 403)
        self.assertEqual(self._post("utts", self.outsider_token, key="IDEM-WRONG-ACTOR").status_code, 403)
        self.assertFalse(self.fx.contracts._utts)

    def test_receiver_stage_and_utt_reject_missing_receiver_authority(self):
        body = self._body()
        del body["receiver_authority"]
        self.assertEqual(self._post("etk-r/verify", self.receiver_token, body).status_code, 403)
        self.assertEqual(self._post("utts", self.sender_token, body, key="IDEM-MISSING-R").status_code, 403)
        self.assertFalse(self.fx.contracts._utts)

    def test_compromised_receiver_key_revoked_blocks_utt(self):
        self.fx.keys.revoke(
            "api-receiver", reason="SANDBOX-COMPROMISE",
            revoked_at=datetime.now(timezone.utc),
        )
        denied = self._post("utts", self.sender_token, key="IDEM-REVOKED-KEY")
        self.assertEqual(denied.status_code, 403, denied.text)
        self.assertFalse(self.fx.contracts._utts)

    def test_sender_signature_tamper_rejected_and_audited(self):
        body = self._body()
        body["sender_authority"]["payload"]["amount_minor"] += 1
        res = self._post("etk-s/verify", self.sender_token, body)
        self.assertEqual(res.status_code, 403)
        self.assertEqual(self.audits.audits()[-1].status_code, 403)
        self.assertNotIn("amount_minor", str(self.audits.audits()[-1].signed_audit.to_dict()))

    def test_valid_sender_signature_without_bank_evidence_is_denied(self):
        import hashlib
        from railone_crypto.canonical_json import canonical_json_bytes
        from railone_crypto.signature_service import ArtifactType
        payload = dict(self.sender.payload)
        del payload["beneficiary_verification"], payload["etk_s_id"]
        sender_id = "ETKS-" + hashlib.sha256(canonical_json_bytes(payload)).hexdigest()[:32].upper()
        signed = self.fx.signatures.sign_artifact(artifact_type=ArtifactType.ETK_S,
            payload={"etk_s_id": sender_id, **payload}, key_id="api-sender",
            issued_at=self.fx.now + timedelta(seconds=5))
        body = self._body()
        body["sender_authority"] = signed.to_dict()
        self.assertEqual(self._post("utts", self.sender_token, body, key="IDEM-NO-BANK-PROOF").status_code, 403)
        self.assertFalse(self.fx.contracts._utts)

    def test_etk_r_bound_to_wrong_etk_s_rejected(self):
        alternate = self.fx.bilateral.issue_sender_authority(
            signed_quote=self.fx.quote, signing_key_id="api-sender",
            beneficiary_verification=beneficiary_evidence(self.signatures, self.fx.quote, self.fx.now),
            authorized_at=self.fx.now + timedelta(seconds=6),
            expires_at=self.fx.now + timedelta(seconds=45),
        )
        body = self._body()
        body["sender_authority"] = alternate.to_dict()
        self.assertEqual(self._post("etk-r/verify", self.receiver_token, body).status_code, 403)
        self.assertEqual(self._post("utts", self.sender_token, body, key="IDEM-WRONG-S").status_code, 403)
        self.assertFalse(self.fx.contracts._utts)

    def test_idempotency_material_mismatch_returns_409(self):
        key = "IDEM-P2P-CONFLICT-001"
        res = self._post("utts", self.sender_token, key=key)
        self.assertEqual(res.status_code, 200, res.text)
        body = self._body()
        body["origin_intent_id"] = "OTHER-INTENT"
        conflict = self._post("utts", self.sender_token, body, key=key)
        self.assertEqual(conflict.status_code, 409, conflict.text)
        self.assertEqual(self.audits.audits()[-1].status_code, 409)
        self.assertEqual(len(self.fx.contracts._utts), 1)

    def test_unconfigured_routes_are_not_exposed(self):
        facade = RailOneApiFacade(
            guard=self.guard,
            history=TransactionHistoryService(InMemoryTransactionHistoryStore()),
            outcomes=InMemoryProviderOutcomeProjectionStore(),
        )
        no_bilateral = TestClient(self.create_app(facade=facade))
        res = no_bilateral.post("/v1/bilateral/p2p/utts", json=self._body(),
                                headers=self._headers(self.sender_token, key="IDEM-NONE-001"))
        self.assertEqual(res.status_code, 404)

    def test_payload_must_not_accept_signing_key_instead_of_envelope(self):
        body = self._body()
        body["sender_authority"] = {"signing_key_id": "api-sender"}
        self.assertEqual(self._post("utts", self.sender_token, body, key="IDEM-KEY-NAME").status_code, 403)

    def test_invalid_idempotency_rejected_before_utt(self):
        self.assertEqual(self._post("utts", self.sender_token, key="").status_code, 403)
        self.assertEqual(self._post("utts", self.sender_token, key="..").status_code, 403)
        self.assertFalse(self.fx.contracts._utts)


if __name__ == "__main__":
    unittest.main()
