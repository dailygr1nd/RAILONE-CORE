"""M-PESA Kenya Daraja B2C sandbox adapter.

The adapter intentionally declares no provider-side idempotency guarantee.
RailOne therefore never resubmits a request left in DISPATCHING/UNKNOWN state.
"""

from __future__ import annotations

import base64
import json
import os
import re
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Protocol

from railone_operations import (
    ProviderExecutionRequest,
    ProviderOutcome,
    ProviderSubmissionResult,
    RejectionDisposition,
)


@dataclass(frozen=True, slots=True)
class MpesaCredentials:
    consumer_key: str = field(repr=False)
    consumer_secret: str = field(repr=False)
    initiator_name: str
    security_credential: str = field(repr=False)
    business_shortcode: str


@dataclass(frozen=True, slots=True)
class MpesaConfig:
    base_url: str = "https://sandbox.safaricom.co.ke"
    oauth_path: str = "/oauth/v1/generate?grant_type=client_credentials"
    b2c_path: str = "/mpesa/b2c/v3/paymentrequest"
    result_url: str = ""
    timeout_url: str = ""
    command_id: str = "BusinessPayment"
    timeout_seconds: int = 15

    def validate(self) -> None:
        if not self.base_url.startswith("https://"):
            raise ValueError("M-PESA base URL must use HTTPS")
        for name, value in (("result_url", self.result_url), ("timeout_url", self.timeout_url)):
            if not value.startswith("https://"):
                raise ValueError(f"M-PESA {name} must use HTTPS")
        if self.command_id not in {"BusinessPayment", "SalaryPayment", "PromotionPayment"}:
            raise ValueError("unsupported M-PESA B2C command")
        if not 1 <= self.timeout_seconds <= 60:
            raise ValueError("M-PESA timeout must be between 1 and 60 seconds")


class MpesaCredentialProvider(Protocol):
    def get(self) -> MpesaCredentials: ...


class EnvironmentMpesaCredentialProvider:
    def get(self) -> MpesaCredentials:
        values = {
            "consumer_key": os.environ.get("RAILONE_MPESA_CONSUMER_KEY", ""),
            "consumer_secret": os.environ.get("RAILONE_MPESA_CONSUMER_SECRET", ""),
            "initiator_name": os.environ.get("RAILONE_MPESA_INITIATOR_NAME", ""),
            "security_credential": os.environ.get("RAILONE_MPESA_SECURITY_CREDENTIAL", ""),
            "business_shortcode": os.environ.get("RAILONE_MPESA_SHORTCODE", ""),
        }
        missing = [name for name, value in values.items() if not value.strip()]
        if missing:
            raise RuntimeError(f"missing M-PESA credentials: {', '.join(missing)}")
        return MpesaCredentials(**values)


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status_code: int
    body: bytes

    def json_object(self) -> dict[str, object]:
        value = json.loads(self.body.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("provider response must be a JSON object")
        return value


class HttpTransport(Protocol):
    def request(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
        timeout_seconds: int,
    ) -> HttpResponse: ...


class UrllibHttpTransport:
    def __init__(self) -> None:
        self._ssl_context = ssl.create_default_context()

    def request(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
        timeout_seconds: int,
    ) -> HttpResponse:
        request = urllib.request.Request(
            url=url, data=body, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(
                request, timeout=timeout_seconds, context=self._ssl_context
            ) as response:
                return HttpResponse(response.status, _bounded_body(response))
        except urllib.error.HTTPError as exc:
            return HttpResponse(exc.code, _bounded_body(exc))


class MpesaOAuthTokenProvider:
    def __init__(
        self,
        *,
        config: MpesaConfig,
        credentials: MpesaCredentialProvider,
        transport: HttpTransport,
    ) -> None:
        self._config = config
        self._credentials = credentials
        self._transport = transport
        self._lock = RLock()
        self._cached: tuple[str, datetime] | None = None

    def get(self, *, at: datetime | None = None) -> str:
        instant = (at or datetime.now(timezone.utc)).astimezone(timezone.utc)
        with self._lock:
            if self._cached is not None and self._cached[1] > instant + timedelta(seconds=30):
                return self._cached[0]
            credentials = self._credentials.get()
            basic = base64.b64encode(
                f"{credentials.consumer_key}:{credentials.consumer_secret}".encode("utf-8")
            ).decode("ascii")
            response = self._transport.request(
                method="GET",
                url=self._config.base_url.rstrip("/") + self._config.oauth_path,
                headers={"Authorization": f"Basic {basic}", "Accept": "application/json"},
                body=None,
                timeout_seconds=self._config.timeout_seconds,
            )
            if response.status_code != 200:
                raise RuntimeError("M-PESA OAuth request was rejected")
            payload = response.json_object()
            token = payload.get("access_token")
            expires_raw = payload.get("expires_in", 3599)
            if not isinstance(token, str) or not token:
                raise RuntimeError("M-PESA OAuth response omitted access_token")
            try:
                expires_in = int(expires_raw)
            except (TypeError, ValueError) as exc:
                raise RuntimeError("M-PESA OAuth expiry is invalid") from exc
            if not 60 <= expires_in <= 86_400:
                raise RuntimeError("M-PESA OAuth expiry is outside policy")
            self._cached = (token, instant + timedelta(seconds=expires_in))
            return token


class MpesaB2CAdapter:
    provider_id = "MPESA-KE"
    supports_idempotency = False

    def __init__(
        self,
        *,
        config: MpesaConfig,
        credentials: MpesaCredentialProvider,
        transport: HttpTransport,
        tokens: MpesaOAuthTokenProvider | None = None,
    ) -> None:
        config.validate()
        self._config = config
        self._credentials = credentials
        self._transport = transport
        self._tokens = tokens or MpesaOAuthTokenProvider(
            config=config, credentials=credentials, transport=transport
        )

    def submit(self, request: ProviderExecutionRequest) -> ProviderSubmissionResult:
        if request.provider_id != self.provider_id:
            raise ValueError("M-PESA adapter received another provider's request")
        if request.rail != "MOBILE_MONEY":
            return _terminal("MPESA_RAIL_UNSUPPORTED")
        if request.currency_from != "KES" or request.currency_to != "KES":
            return _terminal("MPESA_CURRENCY_UNSUPPORTED")
        if request.amount_minor != request.receive_amount_minor:
            return _terminal("MPESA_DOMESTIC_AMOUNT_MISMATCH")
        amount, remainder = divmod(request.amount_minor, 100)
        if remainder or amount <= 0:
            return _terminal("MPESA_WHOLE_KES_REQUIRED")
        msisdn = request.beneficiary_account_reference.strip()
        if re.fullmatch(r"254[17][0-9]{8}", msisdn) is None:
            return _terminal("MPESA_BENEFICIARY_MSISDN_INVALID")
        try:
            credentials = self._credentials.get()
            access_token = self._tokens.get()
        except Exception:
            # Token acquisition happens before the payment endpoint is called,
            # therefore a retry is safe and is not an unknown payment outcome.
            return ProviderSubmissionResult(
                outcome=ProviderOutcome.REJECTED,
                code="MPESA_AUTH_UNAVAILABLE",
                rejection_disposition=RejectionDisposition.RETRYABLE,
            )
        if re.fullmatch(r"[0-9]{5,10}", credentials.business_shortcode) is None:
            return _terminal("MPESA_SHORTCODE_INVALID")
        payload = {
            "InitiatorName": credentials.initiator_name,
            "SecurityCredential": credentials.security_credential,
            "CommandID": self._config.command_id,
            "Amount": amount,
            "PartyA": credentials.business_shortcode,
            "PartyB": msisdn,
            "Remarks": f"RailOne {request.rtt_id}"[:100],
            "QueueTimeOutURL": self._config.timeout_url,
            "ResultURL": self._config.result_url,
            "Occasion": request.idempotency_key[:100],
        }
        response = self._transport.request(
            method="POST",
            url=self._config.base_url.rstrip("/") + self._config.b2c_path,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            body=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            timeout_seconds=self._config.timeout_seconds,
        )
        try:
            result = response.json_object()
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            return _unknown("MPESA_RESPONSE_UNPARSEABLE")
        response_code = str(result.get("ResponseCode", ""))
        if 200 <= response.status_code < 300 and response_code == "0":
            conversation_id = result.get("ConversationID")
            originator_id = result.get("OriginatorConversationID")
            if not all(isinstance(value, str) and value for value in (conversation_id, originator_id)):
                return _unknown("MPESA_ACCEPTANCE_REFERENCE_MISSING")
            return ProviderSubmissionResult(
                outcome=ProviderOutcome.ACCEPTED,
                code="MPESA_ACCEPTED_FOR_PROCESSING",
                external_reference=conversation_id,
                provider_context=(
                    ("amount_minor", str(request.amount_minor)),
                    ("originator_conversation_id", originator_id),
                ),
            )
        if response_code:
            return _terminal(f"MPESA_REJECTED_{_safe_code(response_code)}")
        return _unknown(f"MPESA_HTTP_{response.status_code}_OUTCOME_UNKNOWN")


def _safe_code(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", value.upper()).strip("_")[:80] or "UNKNOWN"


def _bounded_body(response) -> bytes:
    body = response.read(65_537)
    if len(body) > 65_536:
        raise ValueError("M-PESA response exceeds 64 KiB")
    return body


def _terminal(code: str) -> ProviderSubmissionResult:
    return ProviderSubmissionResult(
        outcome=ProviderOutcome.REJECTED,
        code=code,
        rejection_disposition=RejectionDisposition.TERMINAL,
    )


def _unknown(code: str) -> ProviderSubmissionResult:
    return ProviderSubmissionResult(outcome=ProviderOutcome.UNKNOWN, code=code)
