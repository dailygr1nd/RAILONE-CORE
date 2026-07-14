from __future__ import annotations

import importlib.util
import unittest
from datetime import datetime, timedelta, timezone


_HTTP_AVAILABLE = (
    importlib.util.find_spec("fastapi") is not None
    and importlib.util.find_spec("httpx") is not None
)


@unittest.skipUnless(_HTTP_AVAILABLE, "requires the optional RailOne API dependencies")
class HttpTransportTests(unittest.TestCase):
    def setUp(self) -> None:
        from fastapi.testclient import TestClient
        from railone_api.auth import (
            AccessTokenService,
            ActorScopes,
            PrincipalType,
        )
        from railone_api.facade import RailOneApiFacade
        from railone_api.guard import (
            AuthenticatedRequestGuard,
            InMemoryApiAuditStore,
            InMemoryRateLimitStore,
        )
        from railone_api.http import create_app
        from railone_crypto.key_provider import InMemoryEd25519KeyProvider, KeyPurpose
        from railone_crypto.signature_service import SignatureService
        from railone_history import InMemoryTransactionHistoryStore, TransactionHistoryService
        from railone_projection import InMemoryProviderOutcomeProjectionStore

        now = datetime.now(timezone.utc)
        keys = InMemoryEd25519KeyProvider()
        keys.generate(
            key_id="R1AUTH:http", owner_id="R1AUTH",
            purpose=KeyPurpose.ACCESS_TOKEN_SIGNING,
            not_before=now - timedelta(days=1), not_after=now + timedelta(days=30),
        )
        keys.generate(
            key_id="R1CORE:http-audit", owner_id="R1CORE",
            purpose=KeyPurpose.API_AUDIT_SIGNING,
            not_before=now - timedelta(days=1), not_after=now + timedelta(days=30),
        )
        tokens = AccessTokenService(keys=keys, issuer="railone-http-test")
        self.token = tokens.issue(
            principal_id="USER-HTTP-001", principal_type=PrincipalType.HUMAN,
            scopes=ActorScopes(merchant_ids=("MER002",)), key_id="R1AUTH:http",
            at=now,
        )
        guard = AuthenticatedRequestGuard(
            tokens=tokens, rate_limits=InMemoryRateLimitStore(),
            audits=InMemoryApiAuditStore(), signatures=SignatureService(keys),
            audit_signing_key_id="R1CORE:http-audit",
        )
        facade = RailOneApiFacade(
            guard=guard,
            history=TransactionHistoryService(InMemoryTransactionHistoryStore()),
            outcomes=InMemoryProviderOutcomeProjectionStore(),
        )
        self.client = TestClient(create_app(facade=facade))

    def test_health_endpoint_is_non_custodial(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["custody_model"], "NON_CUSTODIAL")

    def test_missing_bearer_token_is_unauthorized(self):
        response = self.client.get("/v1/auth/me")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "BEARER_TOKEN_REQUIRED")

    def test_me_returns_token_derived_scope_and_rate_headers(self):
        response = self.client.get(
            "/v1/auth/me", headers={"Authorization": f"Bearer {self.token}"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["scopes"]["merchant_ids"], ["MER002"])
        self.assertEqual(response.headers["X-RateLimit-Limit"], "60")


if __name__ == "__main__":
    unittest.main()
