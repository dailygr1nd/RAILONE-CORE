"""Optional FastAPI transport for the authenticated RailOne facade.

Install with ``python -m pip install -e '.[api]'``.  Importing the core
``railone_api`` package does not require FastAPI.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.encoders import jsonable_encoder
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from railone_history import SubjectKind, TransactionAccessDeniedError

from .auth import AccessTokenError
from .facade import RailOneApiFacade
from .guard import ApiRateLimitExceededError, RateLimitDecision


_bearer = HTTPBearer(auto_error=False)


def create_app(*, facade: RailOneApiFacade, expose_docs: bool = False) -> FastAPI:
    app = FastAPI(
        title="RailOne Pilot API",
        version="0.8.0",
        description="Non-custodial execution visibility and control boundary",
        docs_url="/docs" if expose_docs else None,
        openapi_url="/openapi.json" if expose_docs else None,
        redoc_url=None,
    )

    @app.exception_handler(AccessTokenError)
    async def access_token_error(_, exc: AccessTokenError):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
            content={"error": {"code": exc.code, "message": "access token rejected"}},
        )

    @app.exception_handler(ApiRateLimitExceededError)
    async def rate_limit_error(_, exc: ApiRateLimitExceededError):
        from fastapi.responses import JSONResponse

        retry_after = max(
            1, int((exc.decision.reset_at - datetime.now(exc.decision.reset_at.tzinfo)).total_seconds())
        )
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": str(retry_after)},
            content={"error": {"code": "API_RATE_LIMIT_EXCEEDED", "message": "request limit reached"}},
        )

    @app.exception_handler(TransactionAccessDeniedError)
    async def transaction_access_error(_, __):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=403,
            content={"error": {"code": "TRANSACTION_ACCESS_DENIED", "message": "subject scope denied"}},
        )

    @app.exception_handler(PermissionError)
    async def permission_error(_, __):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=403,
            content={"error": {"code": "FORBIDDEN", "message": "request denied"}},
        )

    @app.exception_handler(LookupError)
    async def lookup_error(_, __):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=404,
            content={"error": {"code": "NOT_FOUND", "message": "resource not found"}},
        )

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        return {"status": "ok", "custody_model": "NON_CUSTODIAL"}

    @app.get("/v1/auth/me")
    def me(
        response: Response,
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
        request_id: str | None = Header(default=None, alias="X-Request-ID"),
    ):
        principal, decision = facade.me(
            bearer_token=_token(credentials),
            request_id=_request_id(request_id),
        )
        _rate_headers(response, decision)
        return jsonable_encoder(principal)

    @app.get("/v1/transactions/{utt_id}")
    def get_transaction(
        utt_id: str,
        response: Response,
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
        request_id: str | None = Header(default=None, alias="X-Request-ID"),
        access_reason: str | None = Header(default=None, alias="X-Access-Reason"),
    ):
        entry, decision = facade.get_transaction(
            bearer_token=_token(credentials), request_id=_request_id(request_id),
            utt_id=utt_id, access_reason=access_reason,
        )
        _rate_headers(response, decision)
        return jsonable_encoder(entry)

    @app.get("/v1/transactions")
    def list_transactions(
        response: Response,
        subject_kind: SubjectKind = Query(),
        subject_id: str = Query(min_length=1),
        limit: int = Query(default=50, ge=1, le=100),
        cursor: str | None = Query(default=None),
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
        request_id: str | None = Header(default=None, alias="X-Request-ID"),
        access_reason: str | None = Header(default=None, alias="X-Access-Reason"),
    ):
        page, decision = facade.list_transactions(
            bearer_token=_token(credentials), request_id=_request_id(request_id),
            subject_kind=subject_kind, subject_id=subject_id, limit=limit,
            cursor=cursor, access_reason=access_reason,
        )
        _rate_headers(response, decision)
        return jsonable_encoder(page)

    @app.get("/v1/provider-submissions/{submission_id}")
    def get_provider_outcome(
        submission_id: str,
        response: Response,
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
        request_id: str | None = Header(default=None, alias="X-Request-ID"),
        access_reason: str | None = Header(default=None, alias="X-Access-Reason"),
    ):
        outcome, decision = facade.get_provider_outcome(
            bearer_token=_token(credentials), request_id=_request_id(request_id),
            submission_id=submission_id, access_reason=access_reason,
        )
        _rate_headers(response, decision)
        return jsonable_encoder(outcome)

    return app


def _token(credentials: HTTPAuthorizationCredentials | None) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        # Pass through the guard so the unauthenticated attempt is signed and
        # appended to the API audit store.
        return ""
    return credentials.credentials


def _request_id(value: str | None) -> str:
    normalized = value.strip() if value is not None else ""
    if len(normalized) > 128:
        raise HTTPException(status_code=422, detail="X-Request-ID is too long")
    return normalized or f"REQ-{uuid4().hex.upper()}"


def _rate_headers(response: Response, decision: RateLimitDecision) -> None:
    response.headers["X-RateLimit-Limit"] = str(decision.limit)
    response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
    response.headers["X-RateLimit-Reset"] = str(int(decision.reset_at.timestamp()))
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
