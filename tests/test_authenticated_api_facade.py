from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from railone_api import (
    AccessTokenError,
    AccessTokenService,
    ActorScopes,
    ApiAuditOutcome,
    ApiRateLimitExceededError,
    AuthenticatedRequestGuard,
    InMemoryApiAuditStore,
    InMemoryRateLimitStore,
    PrincipalType,
    RailOneApiFacade,
)
from railone_crypto.key_provider import InMemoryEd25519KeyProvider, KeyPurpose
from railone_crypto.signature_service import ArtifactType, SignatureService
from railone_history import (
    InMemoryTransactionHistoryStore,
    SubjectKind,
    TransactionAccessDeniedError,
    TransactionHistoryService,
    TransactionRole,
    TransactionSubjectLink,
    UttTransactionProjection,
)
from railone_projection import (
    InMemoryProviderOutcomeProjectionStore,
    ProviderOutcomeProjection,
    ProviderProgressState,
)


class AuthenticatedApiFacadeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 7, 14, 20, 30, tzinfo=timezone.utc)
        keys = InMemoryEd25519KeyProvider()
        keys.generate(
            key_id="R1AUTH:access:api", owner_id="R1AUTH",
            purpose=KeyPurpose.ACCESS_TOKEN_SIGNING,
            not_before=self.now - timedelta(days=1),
            not_after=self.now + timedelta(days=30),
        )
        keys.generate(
            key_id="R1CORE:audit:api", owner_id="R1CORE",
            purpose=KeyPurpose.API_AUDIT_SIGNING,
            not_before=self.now - timedelta(days=1),
            not_after=self.now + timedelta(days=30),
        )
        self.signatures = SignatureService(keys)
        self.tokens = AccessTokenService(keys=keys, issuer="railone-test")
        self.merchant_token = self.tokens.issue(
            principal_id="MERCHANT-USER-001",
            principal_type=PrincipalType.HUMAN,
            scopes=ActorScopes(merchant_ids=("MER002",), branch_ids=("BR001",)),
            key_id="R1AUTH:access:api", token_id="AT-MERCHANT-001", at=self.now,
        )
        self.operator_token = self.tokens.issue(
            principal_id="OPS-001", principal_type=PrincipalType.OPERATOR,
            scopes=ActorScopes(permissions=("railone.transactions.read:any",)),
            key_id="R1AUTH:access:api", token_id="AT-OPS-001", at=self.now,
        )
        self.history_store = InMemoryTransactionHistoryStore()
        projection = UttTransactionProjection(
            utt_id="UTT-" + "A" * 32, utt_payload_sha256="b" * 64,
            quote_id="QUOTE-001", purpose="SUPPLIER_PAYMENT",
            context_type="MERCHANT", amount_minor=10_000,
            currency_from="KES", receive_amount_minor=9_950,
            currency_to="KES", commercial_state="ACCEPTED",
            accepted_at=self.now, indexed_at=self.now,
        )
        self.history_store.commit(
            projection,
            (
                TransactionSubjectLink(
                    utt_id=projection.utt_id, subject_kind=SubjectKind.MERCHANT_ID,
                    subject_id="MER002", roles=(TransactionRole.ORIGIN_MERCHANT,),
                    linked_at=self.now,
                ),
                TransactionSubjectLink(
                    utt_id=projection.utt_id, subject_kind=SubjectKind.BRANCH_ID,
                    subject_id="BR001", roles=(TransactionRole.ORIGIN_BRANCH,),
                    linked_at=self.now,
                ),
            ),
        )
        self.outcomes = InMemoryProviderOutcomeProjectionStore()
        outcome = ProviderOutcomeProjection(
            submission_id="SUB-001", utt_id=projection.utt_id,
            rtt_id="RTT-" + "B" * 32, provider_id="MPESA-KE",
            state=ProviderProgressState.ACCEPTED_FOR_PROCESSING,
            normalized_code="ACCEPTED_FOR_PROCESSING",
            external_reference="MPS-001", rejection_disposition=None,
            submission_version=3, source_event_id="EVT-001",
            occurred_at=self.now, projected_at=self.now,
        )
        self.outcomes.apply(
            event_id="EVT-001", event_payload_sha256="c" * 64,
            projection=outcome,
        )
        self.audits = InMemoryApiAuditStore()
        self.guard = AuthenticatedRequestGuard(
            tokens=self.tokens, rate_limits=InMemoryRateLimitStore(),
            audits=self.audits, signatures=self.signatures,
            audit_signing_key_id="R1CORE:audit:api",
            requests_per_window=2, window_seconds=60,
        )
        self.facade = RailOneApiFacade(
            guard=self.guard,
            history=TransactionHistoryService(self.history_store),
            outcomes=self.outcomes,
        )

    def test_token_scope_allows_own_merchant_history(self):
        page, _ = self.facade.list_transactions(
            bearer_token=self.merchant_token, request_id="REQ-001",
            subject_kind=SubjectKind.MERCHANT_ID, subject_id="MER002", at=self.now,
        )
        self.assertEqual(len(page.entries), 1)
        self.assertEqual(self.audits.audits()[-1].outcome, ApiAuditOutcome.ALLOWED)

    def test_caller_cannot_supply_another_merchant_scope(self):
        with self.assertRaises(TransactionAccessDeniedError):
            self.facade.list_transactions(
                bearer_token=self.merchant_token, request_id="REQ-002",
                subject_kind=SubjectKind.MERCHANT_ID, subject_id="MER999", at=self.now,
            )
        self.assertEqual(self.audits.audits()[-1].outcome, ApiAuditOutcome.DENIED)

    def test_provider_outcome_requires_access_to_its_utt(self):
        outcome, _ = self.facade.get_provider_outcome(
            bearer_token=self.merchant_token, request_id="REQ-003",
            submission_id="SUB-001", at=self.now,
        )
        self.assertEqual(outcome.provider_id, "MPESA-KE")

    def test_privileged_operator_requires_reason(self):
        with self.assertRaises(TransactionAccessDeniedError):
            self.facade.get_transaction(
                bearer_token=self.operator_token, request_id="REQ-004",
                utt_id="UTT-" + "A" * 32, at=self.now,
            )
        entry, _ = self.facade.get_transaction(
            bearer_token=self.operator_token, request_id="REQ-005",
            utt_id="UTT-" + "A" * 32,
            access_reason="INCIDENT-2026-0714", at=self.now,
        )
        self.assertEqual(entry.transaction.quote_id, "QUOTE-001")

    def test_rate_limit_is_per_principal_and_route(self):
        self.facade.me(bearer_token=self.merchant_token, request_id="REQ-006", at=self.now)
        self.facade.me(bearer_token=self.merchant_token, request_id="REQ-007", at=self.now)
        with self.assertRaises(ApiRateLimitExceededError):
            self.facade.me(bearer_token=self.merchant_token, request_id="REQ-008", at=self.now)
        self.assertEqual(self.audits.audits()[-1].outcome, ApiAuditOutcome.RATE_LIMITED)

    def test_invalid_token_attempt_is_signed_and_audited_without_token_material(self):
        with self.assertRaises(AccessTokenError):
            self.facade.me(bearer_token="not-a-token", request_id="REQ-009", at=self.now)
        audit = self.audits.audits()[-1]
        self.assertEqual(audit.principal_id, "UNAUTHENTICATED")
        self.assertTrue(
            self.signatures.verify_artifact(
                audit.signed_audit,
                expected_artifact_type=ArtifactType.API_REQUEST_AUDIT,
            ).valid
        )
        self.assertNotIn("not-a-token", repr(audit.signed_audit.to_dict()))


if __name__ == "__main__":
    unittest.main()
