from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone

from railone_authority import ExecutionAuthorityService
from railone_contracts import (
    AccountRole,
    AccountType,
    ActorReference,
    ContextType,
    InMemoryContractStore,
    OriginContext,
    PaymentPurpose,
    QuoteAcceptanceCommand,
    QuoteAcceptanceService,
    QuoteService,
    QuoteTerms,
    UttNotFoundError,
)
from railone_partners import (
    AccountBinding, AccountBindingStatus, InMemoryPartnerDirectory,
    PartnerInstitution,
)
from tests.support import endpoint, quote_service
from railone_crypto.key_provider import InMemoryEd25519KeyProvider, KeyPurpose
from railone_crypto.signature_service import ArtifactType, SignatureService
from railone_execution import (
    AttemptState,
    ExecutionPlanningService,
    FailureDisposition,
    InMemoryExecutionStore,
    LinkStatus,
    NoEligibleRouteError,
    PlanNotExecutableError,
    PlanStatus,
    RouteCandidate,
    RttAttemptService,
)


class ExecutionPlanAndRttTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)
        keys = InMemoryEd25519KeyProvider()
        keys.generate(
            key_id="R1CORE:quote:2026-01",
            owner_id="R1CORE",
            purpose=KeyPurpose.QUOTE_SIGNING,
            not_before=self.now - timedelta(days=1),
            not_after=self.now + timedelta(days=90),
        )
        keys.generate(
            key_id="R1CORE:execution:2026-01",
            owner_id="R1CORE",
            purpose=KeyPurpose.EXECUTION_SIGNING,
            not_before=self.now - timedelta(days=1),
            not_after=self.now + timedelta(days=90),
        )
        self.signatures = SignatureService(keys)
        self.contracts = InMemoryContractStore()
        self.executions = InMemoryExecutionStore(self.contracts)
        self.directory = InMemoryPartnerDirectory()
        for institution_id in ("INST-SOURCE", "INST-DEST"):
            self.directory.add_institution(PartnerInstitution(
                institution_id=institution_id, display_name=institution_id,
                country_codes=("KE",), currencies=("KES",),
                supported_roles=(AccountRole.DEBIT, AccountRole.CREDIT),
            ))
        self.directory.add_binding(AccountBinding(
            account_binding_id="BIND-PAYER-001", actor_id="MER002",
            institution_id="INST-SOURCE", role=AccountRole.DEBIT,
            account_type=AccountType.BANK_ACCOUNT, currency="KES",
            display_hint="****1111", contact_binding_id="CONTACT-BIND-PAYER-001",
            attestation_reference="ATTEST-BIND-PAYER-001",
        ))
        self.directory.add_binding(AccountBinding(
            account_binding_id="BIND-BEN-001", actor_id="SUP-001",
            institution_id="INST-DEST", role=AccountRole.CREDIT,
            account_type=AccountType.BANK_ACCOUNT, currency="KES",
            display_hint="****2222", contact_binding_id="CONTACT-BIND-BEN-001",
            attestation_reference="ATTEST-BIND-BEN-001",
        ))
        self.planning = ExecutionPlanningService(
            signatures=self.signatures,
            contracts=self.contracts,
            executions=self.executions,
        )
        self.attempts = RttAttemptService(
            signatures=self.signatures,
            contracts=self.contracts,
            executions=self.executions,
            rtt_signing_key_id="R1CORE:execution:2026-01",
            endpoints=self.directory,
        )

    def _accepted_utt(self, *, max_attempts: int = 5) -> str:
        terms = QuoteTerms(
            request_id=f"REQ-{max_attempts}",
            payer=ActorReference(
                "MERCHANT", "MER002", endpoint("BIND-PAYER-001", AccountRole.DEBIT)
            ),
            beneficiary=ActorReference(
                "SUPPLIER", "SUP-001", endpoint("BIND-BEN-001", AccountRole.CREDIT)
            ),
            purpose=PaymentPurpose.SUPPLIER_PAYMENT,
            amount_minor=250_000,
            currency_from="KES",
            receive_amount_minor=247_500,
            currency_to="KES",
            total_fee_minor=2_500,
            routing_budget_minor=1_000,
            fx_rate="1.000000",
            corridor_id="KE-DOMESTIC",
            service_level="STANDARD",
            routing_policy_id="POLICY-KE-01",
            pricing_version="2026-07",
            max_attempts=max_attempts,
        )
        quote = QuoteService(self.signatures, endpoints=self.directory).issue_quote(
            terms=terms,
            signing_key_id="R1CORE:quote:2026-01",
            issued_at=self.now,
            expires_at=self.now + timedelta(seconds=60),
        )
        service = QuoteAcceptanceService(
            signatures=self.signatures,
            authority=ExecutionAuthorityService(self.signatures),
            store=self.contracts,
            utt_signing_key_id="R1CORE:execution:2026-01",
            authority_signing_key_id="R1CORE:execution:2026-01",
        )
        result = service.accept(
            QuoteAcceptanceCommand(
                signed_quote=quote,
                origin=OriginContext(
                    origin_system="AVIA",
                    origin_intent_id="AVIA-SUPPLIER-001",
                    context_type=ContextType.MERCHANT,
                    purpose=PaymentPurpose.SUPPLIER_PAYMENT,
                    merchant_id="MER002",
                    branch_id="BR001",
                ),
                authorization_method="MERCHANT_ACTOR_ATTESTATION",
                authorization_reference="AUTH-001",
                idempotency_key=f"idem-{max_attempts}",
            ),
            at=self.now + timedelta(seconds=10),
        )
        return result.contract.utt_id

    def _route(
        self,
        route_id: str,
        *,
        latency_ms: int,
        cost_minor: int,
        capacity_minor: int = 2_000_000,
        status: LinkStatus = LinkStatus.UP,
    ) -> RouteCandidate:
        return RouteCandidate(
            route_id=route_id,
            source_institution_id="INST-SOURCE",
            destination_institution_id="INST-DEST",
            rail="MOBILE_MONEY",
            provider=f"PROVIDER-{route_id}",
            adapter=f"adapter-{route_id}",
            currency_from="KES",
            currency_to="KES",
            min_amount_minor=100,
            max_amount_minor=5_000_000,
            latency_ms=latency_ms,
            congestion_bps=500 if route_id == "FAST" else 2_500,
            liquidity_capacity_minor=capacity_minor,
            throughput_headroom_bps=9_000 if route_id == "FAST" else 6_000,
            speed_bps=9_500 if route_id == "FAST" else 6_500,
            estimated_cost_minor=cost_minor,
            link_status=status,
            telemetry_observed_at=self.now,
            telemetry_expires_at=self.now + timedelta(minutes=5),
        )

    def _plan(self, *, max_attempts: int = 5):
        utt_id = self._accepted_utt(max_attempts=max_attempts)
        routes = (
            self._route("SLOW", latency_ms=2_000, cost_minor=400),
            self._route("FAST", latency_ms=100, cost_minor=100),
        )
        plan = self.planning.build_plan(
            utt_id=utt_id,
            candidates=routes,
            at=self.now + timedelta(seconds=20),
        )
        return utt_id, plan

    def test_unknown_utt_cannot_create_a_plan(self) -> None:
        with self.assertRaises(UttNotFoundError):
            self.planning.build_plan(
                utt_id="UTT-UNKNOWN",
                candidates=(self._route("FAST", latency_ms=100, cost_minor=100),),
                at=self.now + timedelta(seconds=20),
            )

    def test_plan_filters_ineligible_routes_and_ranks_deterministically(self) -> None:
        utt_id = self._accepted_utt()
        plan = self.planning.build_plan(
            utt_id=utt_id,
            candidates=(
                self._route("SLOW", latency_ms=2_000, cost_minor=400),
                self._route("DOWN", latency_ms=1, cost_minor=1, status=LinkStatus.DOWN),
                self._route("NO-LIQUIDITY", latency_ms=1, cost_minor=1, capacity_minor=100),
                self._route("FAST", latency_ms=100, cost_minor=100),
            ),
            at=self.now + timedelta(seconds=20),
        )
        self.assertEqual(
            tuple(route.candidate.route_id for route in plan.ranked_routes),
            ("FAST", "SLOW"),
        )
        self.assertGreater(plan.ranked_routes[0].score_bps, plan.ranked_routes[1].score_bps)

    def test_route_cannot_silently_change_selected_endpoint_institutions(self) -> None:
        utt_id = self._accepted_utt()
        route = self._route("WRONG-ENDPOINT", latency_ms=1, cost_minor=1)
        route = replace(route, destination_institution_id="OTHER-INSTITUTION")
        with self.assertRaises(NoEligibleRouteError):
            self.planning.build_plan(
                utt_id=utt_id, candidates=(route,),
                at=self.now + timedelta(seconds=20),
            )

    def test_revoked_account_binding_blocks_rtt_without_mutating_utt(self) -> None:
        utt_id = self._accepted_utt()
        self.planning.build_plan(
            utt_id=utt_id,
            candidates=(self._route("FAST", latency_ms=100, cost_minor=100),),
            at=self.now + timedelta(seconds=20),
        )
        before = self.contracts.require_utt(utt_id)
        self.directory.set_binding_status(
            "BIND-PAYER-001", AccountBindingStatus.REVOKED
        )
        with self.assertRaises(PermissionError):
            self.attempts.start_next(
                utt_id=utt_id, at=self.now + timedelta(seconds=21)
            )
        self.assertIs(self.contracts.require_utt(utt_id), before)

    def test_duplicate_route_identifiers_are_rejected(self) -> None:
        utt_id = self._accepted_utt()
        route = self._route("DUPLICATE", latency_ms=100, cost_minor=100)
        with self.assertRaisesRegex(ValueError, "route_id must be unique"):
            self.planning.build_plan(
                utt_id=utt_id,
                candidates=(route, route),
                at=self.now + timedelta(seconds=20),
            )

    def test_first_rtt_is_signed_and_contains_no_second_customer_charge(self) -> None:
        utt_id, plan = self._plan()
        attempt = self.attempts.start_next(
            utt_id=utt_id, at=self.now + timedelta(seconds=21)
        )
        self.assertEqual(attempt.utt_id, utt_id)
        self.assertEqual(attempt.plan_id, plan.plan_id)
        self.assertEqual(attempt.route_id, "FAST")
        self.assertTrue(
            self.signatures.verify_artifact(
                attempt.signed_rtt, expected_artifact_type=ArtifactType.RTT
            ).valid
        )
        payload = attempt.signed_rtt.payload
        for forbidden in ("customer_fee_minor", "total_fee_minor", "pricing_model"):
            self.assertNotIn(forbidden, payload)
        self.assertEqual(payload["custody_model"], "NON_CUSTODIAL")
        with self.assertRaises(TypeError):
            payload["birth_state"] = "SUCCEEDED"

    def test_retry_uses_same_utt_and_preserves_attempt_lineage(self) -> None:
        utt_id, _ = self._plan()
        first = self.attempts.start_next(
            utt_id=utt_id, at=self.now + timedelta(seconds=21)
        )
        self.attempts.record_failure(
            rtt_id=first.rtt_id,
            failure_code="PROVIDER_UNAVAILABLE",
            disposition=FailureDisposition.RETRYABLE,
            actual_cost_minor=50,
            at=self.now + timedelta(seconds=22),
        )
        second = self.attempts.start_next(
            utt_id=utt_id, at=self.now + timedelta(seconds=23)
        )
        self.assertEqual(second.utt_id, first.utt_id)
        self.assertEqual(second.route_id, "SLOW")
        self.assertEqual(second.signed_rtt.payload["previous_rtt_id"], first.rtt_id)
        self.assertEqual(second.signed_rtt.payload["previous_route_id"], "FAST")
        self.assertEqual(second.signed_rtt.payload["replay_generation"], 1)

    def test_unknown_provider_outcome_blocks_duplicate_retry(self) -> None:
        utt_id, _ = self._plan()
        first = self.attempts.start_next(
            utt_id=utt_id, at=self.now + timedelta(seconds=21)
        )
        plan = self.attempts.record_failure(
            rtt_id=first.rtt_id,
            failure_code="PROVIDER_TIMEOUT_AFTER_SUBMIT",
            disposition=FailureDisposition.RECONCILIATION_REQUIRED,
            actual_cost_minor=0,
            at=self.now + timedelta(seconds=22),
        )
        self.assertEqual(plan.status, PlanStatus.RECONCILIATION_REQUIRED)
        self.assertEqual(
            self.executions.require_attempt(first.rtt_id).state,
            AttemptState.RECONCILIATION_REQUIRED,
        )
        with self.assertRaisesRegex(PlanNotExecutableError, "RECONCILIATION_REQUIRED"):
            self.attempts.start_next(
                utt_id=utt_id, at=self.now + timedelta(seconds=23)
            )

    def test_terminal_failure_blocks_further_routes(self) -> None:
        utt_id, _ = self._plan()
        first = self.attempts.start_next(
            utt_id=utt_id, at=self.now + timedelta(seconds=21)
        )
        plan = self.attempts.record_failure(
            rtt_id=first.rtt_id,
            failure_code="BENEFICIARY_INVALID",
            disposition=FailureDisposition.TERMINAL,
            actual_cost_minor=0,
            at=self.now + timedelta(seconds=22),
        )
        self.assertEqual(plan.status, PlanStatus.FAILED)
        with self.assertRaises(PlanNotExecutableError):
            self.attempts.start_next(
                utt_id=utt_id, at=self.now + timedelta(seconds=23)
            )

    def test_attempt_cap_exhausts_the_plan(self) -> None:
        utt_id, _ = self._plan(max_attempts=1)
        first = self.attempts.start_next(
            utt_id=utt_id, at=self.now + timedelta(seconds=21)
        )
        plan = self.attempts.record_failure(
            rtt_id=first.rtt_id,
            failure_code="TEMPORARY_FAILURE",
            disposition=FailureDisposition.RETRYABLE,
            actual_cost_minor=0,
            at=self.now + timedelta(seconds=22),
        )
        self.assertEqual(plan.status, PlanStatus.EXHAUSTED)

    def test_success_finalizes_exactly_one_route(self) -> None:
        utt_id, _ = self._plan()
        attempt = self.attempts.start_next(
            utt_id=utt_id, at=self.now + timedelta(seconds=21)
        )
        plan = self.attempts.record_success(
            rtt_id=attempt.rtt_id,
            actual_cost_minor=100,
            at=self.now + timedelta(seconds=22),
        )
        self.assertEqual(plan.status, PlanStatus.FINALIZED)
        self.assertEqual(plan.successful_route_id, "FAST")
        self.assertEqual(plan.routing_cost_spent_minor, 100)
        self.assertEqual(
            self.executions.require_attempt(attempt.rtt_id).state,
            AttemptState.SUCCEEDED,
        )

    def test_plan_is_an_immutable_snapshot(self) -> None:
        _, plan = self._plan()
        with self.assertRaises(FrozenInstanceError):
            plan.status = PlanStatus.FAILED


if __name__ == "__main__":
    unittest.main()
