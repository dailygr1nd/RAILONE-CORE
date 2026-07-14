"""Hardened transport boundary; provider adapters never call HTTP libraries directly."""

from __future__ import annotations

import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Mapping, Protocol
from urllib.parse import urlparse


class InstitutionTransportError(RuntimeError):
    """Transport failed and the remote processing outcome may be unknown."""


@dataclass(frozen=True, slots=True)
class InstitutionHttpRequest:
    method: str
    url: str
    headers: Mapping[str, str] = field(default_factory=dict, repr=False)
    body: bytes = field(default=b"", repr=False)
    timeout_seconds: int = 15


@dataclass(frozen=True, slots=True)
class InstitutionHttpResponse:
    status_code: int
    headers: Mapping[str, str] = field(repr=False)
    body: bytes = field(repr=False)


class InstitutionTransport(Protocol):
    def send(self, request: InstitutionHttpRequest) -> InstitutionHttpResponse: ...


class UrllibInstitutionTransport:
    def __init__(
        self,
        *,
        ssl_context: ssl.SSLContext,
        allowed_hosts: frozenset[str],
        max_request_bytes: int = 1_000_000,
        max_response_bytes: int = 1_000_000,
    ) -> None:
        self._ssl_context = ssl_context
        self._allowed_hosts = frozenset(host.lower() for host in allowed_hosts)
        if not self._allowed_hosts:
            raise ValueError("institution transport requires an explicit host allowlist")
        if ssl_context.verify_mode != ssl.CERT_REQUIRED or not ssl_context.check_hostname:
            raise ValueError("institution TLS context must verify certificates and hostnames")
        if ssl_context.minimum_version < ssl.TLSVersion.TLSv1_2:
            raise ValueError("institution TLS context must require TLS 1.2 or newer")
        self._max_request_bytes = max_request_bytes
        self._max_response_bytes = max_response_bytes

    def send(self, request: InstitutionHttpRequest) -> InstitutionHttpResponse:
        parsed = urlparse(request.url)
        if parsed.scheme.lower() != "https" or not parsed.hostname:
            raise ValueError("institution transport requires an absolute HTTPS URL")
        if parsed.hostname.lower() not in self._allowed_hosts:
            raise PermissionError("institution destination host is not allowlisted")
        if request.method.upper() not in {"GET", "POST"}:
            raise ValueError("institution transport permits only GET and POST")
        if not 1 <= request.timeout_seconds <= 300:
            raise ValueError("transport timeout must be between 1 and 300 seconds")
        if len(request.body) > self._max_request_bytes:
            raise ValueError("institution request exceeds configured size limit")
        outgoing = urllib.request.Request(
            request.url,
            data=request.body or None,
            headers=dict(request.headers),
            method=request.method.upper(),
        )
        try:
            opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=self._ssl_context),
                _NoRedirectHandler(),
            )
            with opener.open(outgoing, timeout=request.timeout_seconds) as response:
                body = response.read(self._max_response_bytes + 1)
                if len(body) > self._max_response_bytes:
                    raise InstitutionTransportError("institution response exceeds configured size limit")
                return InstitutionHttpResponse(
                    status_code=response.status,
                    headers=dict(response.headers.items()),
                    body=body,
                )
        except urllib.error.HTTPError as exc:
            body = exc.read(self._max_response_bytes + 1)
            if len(body) > self._max_response_bytes:
                raise InstitutionTransportError("institution error response exceeds configured size limit") from exc
            return InstitutionHttpResponse(exc.code, dict(exc.headers.items()), body)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise InstitutionTransportError("institution transport failed; outcome is unknown") from exc


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None
