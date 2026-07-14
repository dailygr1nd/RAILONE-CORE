"""Authentication strategies for institution requests without exposing credentials."""

from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from .models import AdapterEnvironment
from .transport import InstitutionHttpRequest


class AccessTokenProvider(Protocol):
    def access_token(self) -> str: ...


class ProofOfPossessionProvider(Protocol):
    def proof(self, *, method: str, url: str, access_token: str) -> str: ...


class InstitutionAuthStrategy(Protocol):
    def authenticate(self, request: InstitutionHttpRequest) -> InstitutionHttpRequest: ...


class SimulationNoAuth:
    def __init__(self, environment: AdapterEnvironment) -> None:
        if environment is not AdapterEnvironment.SANDBOX:
            raise ValueError("unauthenticated institution transport is sandbox-only")

    def authenticate(self, request: InstitutionHttpRequest) -> InstitutionHttpRequest:
        return request


class BearerTokenAuth:
    def __init__(
        self,
        token_provider: AccessTokenProvider,
        *,
        proof_provider: ProofOfPossessionProvider | None = None,
    ) -> None:
        self._tokens = token_provider
        self._proofs = proof_provider

    def authenticate(self, request: InstitutionHttpRequest) -> InstitutionHttpRequest:
        token = self._tokens.access_token()
        if not isinstance(token, str) or not token.strip() or any(char.isspace() for char in token):
            raise PermissionError("token provider returned an invalid access token")
        headers = dict(request.headers)
        headers["Authorization"] = f"Bearer {token}"
        if self._proofs is not None:
            headers["DPoP"] = self._proofs.proof(
                method=request.method.upper(), url=request.url, access_token=token
            )
        return replace(request, headers=headers)
