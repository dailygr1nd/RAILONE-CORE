from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from railone_api import (
    AccessTokenError,
    AccessTokenService,
    ActorScopes,
    InMemoryTokenRevocationStore,
    PrincipalType,
)
from railone_crypto.key_provider import InMemoryEd25519KeyProvider, KeyPurpose


class ApiAuthenticationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 7, 14, 20, 0, tzinfo=timezone.utc)
        self.keys = InMemoryEd25519KeyProvider()
        self.keys.generate(
            key_id="R1AUTH:access:2026-01", owner_id="R1AUTH",
            purpose=KeyPurpose.ACCESS_TOKEN_SIGNING,
            not_before=self.now - timedelta(days=1),
            not_after=self.now + timedelta(days=30),
        )
        self.keys.generate(
            key_id="R1CORE:quote:not-token", owner_id="R1CORE",
            purpose=KeyPurpose.QUOTE_SIGNING,
            not_before=self.now - timedelta(days=1),
            not_after=self.now + timedelta(days=30),
        )
        self.revocations = InMemoryTokenRevocationStore()
        self.tokens = AccessTokenService(
            keys=self.keys, issuer="https://identity.railone.africa",
            revocations=self.revocations,
        )

    def _issue(self, **overrides):
        values = {
            "principal_id": "USER-001",
            "principal_type": PrincipalType.HUMAN,
            "scopes": ActorScopes(
                continuity_uid="CUID-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                merchant_ids=("MER002",), branch_ids=("BR001",),
            ),
            "key_id": "R1AUTH:access:2026-01",
            "token_id": "AT-TEST-001",
            "at": self.now,
        }
        values.update(overrides)
        return self.tokens.issue(**values)

    def test_ed25519_token_round_trip_preserves_separate_actor_scopes(self):
        token = self._issue()
        principal = self.tokens.verify(token, at=self.now + timedelta(seconds=1))
        self.assertEqual(principal.scopes.continuity_uid, "CUID-" + "A" * 32)
        self.assertEqual(principal.scopes.merchant_ids, ("MER002",))
        self.assertEqual(principal.scopes.branch_ids, ("BR001",))
        self.assertNotIn("MER002", principal.scopes.continuity_uid)

    def test_token_cannot_be_signed_with_quote_key(self):
        with self.assertRaises(PermissionError):
            self._issue(key_id="R1CORE:quote:not-token")

    def test_tampered_token_is_rejected(self):
        token = self._issue()
        header, claims, signature = token.split(".")
        tampered = header + "." + claims[:-1] + ("A" if claims[-1] != "A" else "B") + "." + signature
        with self.assertRaises(AccessTokenError):
            self.tokens.verify(tampered, at=self.now)

    def test_expired_token_is_rejected_after_clock_skew(self):
        token = self._issue(ttl_seconds=60)
        with self.assertRaisesRegex(AccessTokenError, "TOKEN_EXPIRED"):
            self.tokens.verify(token, at=self.now + timedelta(seconds=91))

    def test_revoked_token_is_rejected(self):
        token = self._issue()
        self.tokens.revoke(token=token, reason="SESSION_TERMINATED", at=self.now)
        with self.assertRaisesRegex(AccessTokenError, "TOKEN_REVOKED"):
            self.tokens.verify(token, at=self.now + timedelta(seconds=1))

    def test_duplicate_or_empty_actor_scopes_are_rejected(self):
        with self.assertRaises(ValueError):
            self._issue(scopes=ActorScopes(merchant_ids=("MER002", "mer002")))
        with self.assertRaises(ValueError):
            self._issue(scopes=ActorScopes(branch_ids=("",)))

    def test_privileged_permission_requires_operator_principal(self):
        with self.assertRaises(ValueError):
            self._issue(
                principal_type=PrincipalType.HUMAN,
                scopes=ActorScopes(permissions=("railone.transactions.read:any",)),
            )


if __name__ == "__main__":
    unittest.main()
