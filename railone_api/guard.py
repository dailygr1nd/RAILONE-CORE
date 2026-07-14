"""Authentication, rate limiting, and signed API request audit."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from threading import RLock
from typing import Callable, Protocol, TypeVar

from railone_crypto.canonical_json import canonical_json_bytes
from railone_crypto.signature_service import ArtifactType, SignatureEnvelope, SignatureService

from .auth import AccessTokenError, AccessTokenService, AuthenticatedPrincipal


class ApiAuditOutcome(StrEnum):
    ALLOWED = "ALLOWED"
    DENIED = "DENIED"
    RATE_LIMITED = "RATE_LIMITED"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class ApiRequest:
    request_id: str
    method: str
    route_template: str
    access_reason: str | None = None


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    reset_at: datetime


@dataclass(frozen=True, slots=True)
class ApiRequestAudit:
    audit_id: str
    request_id: str
    principal_id: str
    token_id: str | None
    method: str
    route_template: str
    outcome: ApiAuditOutcome
    status_code: int
    reason_code: str
    occurred_at: datetime
    signed_audit: SignatureEnvelope


class RateLimitStore(Protocol):
    def consume(
        self, *, scope_key: str, limit: int, window_seconds: int, at: datetime
    ) -> RateLimitDecision: ...


class ApiAuditStore(Protocol):
    def append(self, audit: ApiRequestAudit) -> None: ...


class InMemoryRateLimitStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._windows: dict[str, tuple[datetime, int, int]] = {}

    def consume(
        self, *, scope_key: str, limit: int, window_seconds: int, at: datetime
    ) -> RateLimitDecision:
        _rate_policy(limit, window_seconds)
        with self._lock:
            current = self._windows.get(scope_key)
            if current is None or current[0] + timedelta(seconds=current[2]) <= at:
                started_at, count = at, 1
            else:
                started_at, count = current[0], current[1] + 1
            self._windows[scope_key] = (started_at, count, window_seconds)
            reset_at = started_at + timedelta(seconds=window_seconds)
            return RateLimitDecision(
                allowed=count <= limit,
                limit=limit,
                remaining=max(0, limit - count),
                reset_at=reset_at,
            )


class InMemoryApiAuditStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._audits: dict[str, ApiRequestAudit] = {}

    def append(self, audit: ApiRequestAudit) -> None:
        with self._lock:
            if audit.audit_id in self._audits:
                raise RuntimeError("API audit identifier collision")
            self._audits[audit.audit_id] = audit

    def audits(self) -> tuple[ApiRequestAudit, ...]:
        with self._lock:
            return tuple(self._audits.values())


class ApiRateLimitExceededError(RuntimeError):
    def __init__(self, decision: RateLimitDecision) -> None:
        super().__init__("API_RATE_LIMIT_EXCEEDED")
        self.decision = decision


T = TypeVar("T")


class AuthenticatedRequestGuard:
    def __init__(
        self,
        *,
        tokens: AccessTokenService,
        rate_limits: RateLimitStore,
        audits: ApiAuditStore,
        signatures: SignatureService,
        audit_signing_key_id: str,
        requests_per_window: int = 60,
        window_seconds: int = 60,
    ) -> None:
        _rate_policy(requests_per_window, window_seconds)
        self._tokens = tokens
        self._rate_limits = rate_limits
        self._audits = audits
        self._signatures = signatures
        self._audit_signing_key_id = audit_signing_key_id
        self._limit = requests_per_window
        self._window_seconds = window_seconds

    def execute(
        self,
        *,
        bearer_token: str,
        request: ApiRequest,
        operation: Callable[[AuthenticatedPrincipal], T],
        at: datetime | None = None,
    ) -> tuple[T, RateLimitDecision]:
        instant = _instant(at)
        _validate_request(request)
        principal: AuthenticatedPrincipal | None = None
        try:
            principal = self._tokens.verify(bearer_token, at=instant)
        except AccessTokenError as exc:
            self._audit(
                request=request, principal=None, outcome=ApiAuditOutcome.DENIED,
                status_code=401, reason_code=exc.code, at=instant,
            )
            raise
        decision = self._rate_limits.consume(
            scope_key=f"{principal.principal_id}:{request.route_template}",
            limit=self._limit, window_seconds=self._window_seconds, at=instant,
        )
        if not decision.allowed:
            self._audit(
                request=request, principal=principal,
                outcome=ApiAuditOutcome.RATE_LIMITED,
                status_code=429, reason_code="API_RATE_LIMIT_EXCEEDED", at=instant,
            )
            raise ApiRateLimitExceededError(decision)
        try:
            result = operation(principal)
        except PermissionError as exc:
            self._audit(
                request=request, principal=principal, outcome=ApiAuditOutcome.DENIED,
                status_code=403, reason_code=type(exc).__name__.upper(), at=instant,
            )
            raise
        except LookupError as exc:
            self._audit(
                request=request, principal=principal, outcome=ApiAuditOutcome.DENIED,
                status_code=404, reason_code=type(exc).__name__.upper(), at=instant,
            )
            raise
        except Exception as exc:
            self._audit(
                request=request, principal=principal, outcome=ApiAuditOutcome.ERROR,
                status_code=500, reason_code=type(exc).__name__.upper(), at=instant,
            )
            raise
        self._audit(
            request=request, principal=principal, outcome=ApiAuditOutcome.ALLOWED,
            status_code=200, reason_code="REQUEST_ALLOWED", at=instant,
        )
        return result, decision

    def _audit(
        self,
        *,
        request: ApiRequest,
        principal: AuthenticatedPrincipal | None,
        outcome: ApiAuditOutcome,
        status_code: int,
        reason_code: str,
        at: datetime,
    ) -> None:
        core = {
            "request_id": request.request_id,
            "principal_id": principal.principal_id if principal else "UNAUTHENTICATED",
            "token_id": principal.token_id if principal else None,
            "method": request.method.upper(),
            "route_template": request.route_template,
            "outcome": outcome.value,
            "status_code": status_code,
            "reason_code": reason_code,
            "occurred_at": int(at.timestamp()),
        }
        audit_id = "APIAUD-" + hashlib.sha256(
            canonical_json_bytes(core)
        ).hexdigest().upper()[:32]
        payload = {"audit_id": audit_id, **core}
        signed = self._signatures.sign_artifact(
            artifact_type=ArtifactType.API_REQUEST_AUDIT,
            payload=payload,
            key_id=self._audit_signing_key_id,
            issued_at=at,
        )
        self._audits.append(
            ApiRequestAudit(
                audit_id=audit_id, request_id=request.request_id,
                principal_id=core["principal_id"], token_id=core["token_id"],
                method=core["method"], route_template=request.route_template,
                outcome=outcome, status_code=status_code, reason_code=reason_code,
                occurred_at=at, signed_audit=signed,
            )
        )


def _instant(value: datetime | None) -> datetime:
    instant = value or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("API request timestamp must be timezone-aware")
    return instant.astimezone(timezone.utc)


def _rate_policy(limit: int, window_seconds: int) -> None:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 10_000:
        raise ValueError("rate limit must be between 1 and 10000")
    if (
        isinstance(window_seconds, bool)
        or not isinstance(window_seconds, int)
        or not 1 <= window_seconds <= 3600
    ):
        raise ValueError("rate-limit window must be between 1 and 3600 seconds")


def _validate_request(request: ApiRequest) -> None:
    if not isinstance(request, ApiRequest):
        raise TypeError("request must be an ApiRequest")
    if not request.request_id.strip() or len(request.request_id) > 128:
        raise ValueError("request_id must contain 1 to 128 characters")
    if request.method.upper() not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        raise ValueError("unsupported HTTP method")
    if (
        not request.route_template.startswith("/")
        or len(request.route_template) > 256
        or "?" in request.route_template
    ):
        raise ValueError("route_template must be a normalized route without query data")
