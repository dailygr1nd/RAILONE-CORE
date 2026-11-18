"""Authenticated application boundary used by HTTP and future transports."""

from __future__ import annotations

from datetime import datetime, timezone

from railone_history import SubjectKind, TransactionHistoryService
from railone_projection import ProviderOutcomeProjectionStore

from .auth import AuthenticatedPrincipal
from .bilateral import BilateralP2PApi
from .guard import ApiRequest, AuthenticatedRequestGuard, RateLimitDecision


class RailOneApiFacade:
    def __init__(
        self,
        *,
        guard: AuthenticatedRequestGuard,
        history: TransactionHistoryService,
        outcomes: ProviderOutcomeProjectionStore,
        avia_merchant=None,
        bilateral_p2p: BilateralP2PApi | None = None,
    ) -> None:
        self._guard = guard
        self._history = history
        self._outcomes = outcomes
        self.avia_merchant = avia_merchant
        self._bilateral_p2p = bilateral_p2p

    @property
    def bilateral_p2p_enabled(self) -> bool:
        return self._bilateral_p2p is not None

    def create_avia_utt(self, *, bearer_token, request_id, body, idempotency_key, at=None):
        if self.avia_merchant is None:
            raise PermissionError("AVIA_API_NOT_CONFIGURED")
        instant = at or datetime.now(timezone.utc)
        return self._guard.execute(
            bearer_token=bearer_token, request=ApiRequest(request_id, "POST", "/v1/avia/merchant/utts"),
            operation=lambda principal: self.avia_merchant.create(principal, body, idempotency_key, instant),
            at=instant)

    def verify_sender_intent(self, *, bearer_token: str, request_id: str,
                             body: dict, at: datetime | None = None):
        instant = at or datetime.now(timezone.utc)
        return self._guard.execute(
            bearer_token=bearer_token,
            request=ApiRequest(request_id, "POST", "/v1/bilateral/p2p/etk-s/verify"),
            operation=lambda principal: self._require_bilateral().verify_sender(
                principal=principal, request=body, at=instant,
            ), at=instant,
        )

    def verify_receiver_acceptance(self, *, bearer_token: str, request_id: str,
                                   body: dict, at: datetime | None = None):
        instant = at or datetime.now(timezone.utc)
        return self._guard.execute(
            bearer_token=bearer_token,
            request=ApiRequest(request_id, "POST", "/v1/bilateral/p2p/etk-r/verify"),
            operation=lambda principal: self._require_bilateral().verify_receiver(
                principal=principal, request=body, at=instant,
            ), at=instant,
        )

    def create_bilateral_utt(self, *, bearer_token: str, request_id: str,
                             body: dict, idempotency_key: str,
                             at: datetime | None = None):
        instant = at or datetime.now(timezone.utc)
        return self._guard.execute(
            bearer_token=bearer_token,
            request=ApiRequest(request_id, "POST", "/v1/bilateral/p2p/utts"),
            operation=lambda principal: self._require_bilateral().create_utt(
                principal=principal, request=body, idempotency_key=idempotency_key,
                at=instant,
            ), at=instant,
        )

    def _require_bilateral(self) -> BilateralP2PApi:
        if self._bilateral_p2p is None:
            raise PermissionError("BILATERAL_API_NOT_CONFIGURED")
        return self._bilateral_p2p

    def me(
        self, *, bearer_token: str, request_id: str, at: datetime | None = None
    ) -> tuple[AuthenticatedPrincipal, RateLimitDecision]:
        return self._guard.execute(
            bearer_token=bearer_token,
            request=ApiRequest(request_id, "GET", "/v1/auth/me"),
            operation=lambda principal: principal,
            at=at,
        )

    def get_transaction(
        self,
        *,
        bearer_token: str,
        request_id: str,
        utt_id: str,
        access_reason: str | None = None,
        at: datetime | None = None,
    ):
        return self._guard.execute(
            bearer_token=bearer_token,
            request=ApiRequest(
                request_id, "GET", "/v1/transactions/{utt_id}", access_reason
            ),
            operation=lambda principal: self._history.get_by_utt(
                utt_id=utt_id,
                access=principal.scopes.transaction_context(
                    principal_id=principal.principal_id,
                    access_reason=access_reason,
                ),
                at=at,
            ),
            at=at,
        )

    def list_transactions(
        self,
        *,
        bearer_token: str,
        request_id: str,
        subject_kind: SubjectKind,
        subject_id: str,
        limit: int = 50,
        cursor: str | None = None,
        access_reason: str | None = None,
        at: datetime | None = None,
    ):
        return self._guard.execute(
            bearer_token=bearer_token,
            request=ApiRequest(
                request_id, "GET", "/v1/transactions", access_reason
            ),
            operation=lambda principal: self._history.list_by_subject(
                subject_kind=subject_kind,
                subject_id=subject_id,
                access=principal.scopes.transaction_context(
                    principal_id=principal.principal_id,
                    access_reason=access_reason,
                ),
                limit=limit,
                cursor=cursor,
                at=at,
            ),
            at=at,
        )

    def get_provider_outcome(
        self,
        *,
        bearer_token: str,
        request_id: str,
        submission_id: str,
        access_reason: str | None = None,
        at: datetime | None = None,
    ):
        def operation(principal: AuthenticatedPrincipal):
            projection = self._outcomes.get(submission_id)
            if projection is None:
                raise LookupError(f"provider outcome not found: {submission_id}")
            self._history.get_by_utt(
                utt_id=projection.utt_id,
                access=principal.scopes.transaction_context(
                    principal_id=principal.principal_id,
                    access_reason=access_reason,
                ),
                at=at,
            )
            return projection

        return self._guard.execute(
            bearer_token=bearer_token,
            request=ApiRequest(
                request_id,
                "GET",
                "/v1/provider-submissions/{submission_id}",
                access_reason,
            ),
            operation=operation,
            at=at,
        )
