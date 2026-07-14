"""Authenticated application boundary used by HTTP and future transports."""

from __future__ import annotations

from datetime import datetime

from railone_history import SubjectKind, TransactionHistoryService
from railone_projection import ProviderOutcomeProjectionStore

from .auth import AuthenticatedPrincipal
from .guard import ApiRequest, AuthenticatedRequestGuard, RateLimitDecision


class RailOneApiFacade:
    def __init__(
        self,
        *,
        guard: AuthenticatedRequestGuard,
        history: TransactionHistoryService,
        outcomes: ProviderOutcomeProjectionStore,
    ) -> None:
        self._guard = guard
        self._history = history
        self._outcomes = outcomes

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
