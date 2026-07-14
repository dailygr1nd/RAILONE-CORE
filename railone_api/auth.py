"""Short-lived Ed25519 JWT access tokens for the RailOne API boundary."""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Protocol
from uuid import uuid4

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from railone_crypto.key_provider import KeyPurpose, KeyStatus, SigningKeyProvider
from railone_history import TransactionReadContext
from railone_history import READ_ANY_PERMISSION


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def _instant(value: datetime | None) -> datetime:
    instant = value or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("access-token timestamp must be timezone-aware")
    return instant.astimezone(timezone.utc)


def _normalized_ids(name: str, values: tuple[str, ...]) -> tuple[str, ...]:
    if any(not isinstance(value, str) for value in values):
        raise TypeError(f"{name} must contain strings")
    normalized = tuple(sorted({value.strip().upper() for value in values if value.strip()}))
    if len(normalized) != len(values):
        raise ValueError(f"{name} must contain unique non-empty identifiers")
    if any(len(value) > 128 for value in normalized):
        raise ValueError(f"{name} identifiers cannot exceed 128 characters")
    return normalized


def _normalized_permissions(values: tuple[str, ...]) -> tuple[str, ...]:
    if any(not isinstance(value, str) for value in values):
        raise TypeError("permissions must contain strings")
    normalized = tuple(sorted({value.strip() for value in values if value.strip()}))
    if len(normalized) != len(values):
        raise ValueError("permissions must contain unique non-empty values")
    if any(len(value) > 128 for value in normalized):
        raise ValueError("permissions cannot exceed 128 characters")
    return normalized


def _epoch_claim(claims: Mapping[str, object], name: str) -> datetime:
    value = claims[name]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer epoch timestamp")
    return datetime.fromtimestamp(value, tz=timezone.utc)


def _validate_principal_scope(
    principal_type: "PrincipalType", scopes: "ActorScopes"
) -> None:
    if READ_ANY_PERMISSION in scopes.permissions and principal_type is not PrincipalType.OPERATOR:
        raise ValueError("privileged transaction permission requires OPERATOR principal type")
    if principal_type is PrincipalType.MERCHANT_SERVICE and not scopes.merchant_ids:
        raise ValueError("merchant service requires at least one merchant scope")
    if principal_type is PrincipalType.PARTNER_SERVICE and not scopes.partner_ids:
        raise ValueError("partner service requires at least one partner scope")


class PrincipalType(StrEnum):
    HUMAN = "HUMAN"
    MERCHANT_SERVICE = "MERCHANT_SERVICE"
    PARTNER_SERVICE = "PARTNER_SERVICE"
    OPERATOR = "OPERATOR"


@dataclass(frozen=True, slots=True)
class ActorScopes:
    continuity_uid: str | None = None
    merchant_ids: tuple[str, ...] = ()
    branch_ids: tuple[str, ...] = ()
    partner_ids: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()

    def normalized(self) -> "ActorScopes":
        if self.continuity_uid is not None and not isinstance(self.continuity_uid, str):
            raise TypeError("continuity_uid must be a string")
        continuity_uid = (
            self.continuity_uid.strip().upper()
            if self.continuity_uid is not None else None
        )
        if continuity_uid is not None and re.fullmatch(
            r"CUID-[A-Z2-7]{32}", continuity_uid
        ) is None:
            raise ValueError("continuity_uid must be a RailOne ContUID")
        normalized = ActorScopes(
            continuity_uid=continuity_uid,
            merchant_ids=_normalized_ids("merchant_ids", self.merchant_ids),
            branch_ids=_normalized_ids("branch_ids", self.branch_ids),
            partner_ids=_normalized_ids("partner_ids", self.partner_ids),
            permissions=_normalized_permissions(self.permissions),
        )
        total_scopes = (
            len(normalized.merchant_ids) + len(normalized.branch_ids)
            + len(normalized.partner_ids) + len(normalized.permissions)
            + (1 if normalized.continuity_uid else 0)
        )
        if total_scopes > 200:
            raise ValueError("access token exceeds the actor-scope limit")
        return normalized

    def transaction_context(
        self, *, principal_id: str, access_reason: str | None
    ) -> TransactionReadContext:
        normalized = self.normalized()
        return TransactionReadContext(
            principal_id=principal_id,
            continuity_uid=normalized.continuity_uid,
            merchant_ids=normalized.merchant_ids,
            branch_ids=normalized.branch_ids,
            partner_ids=normalized.partner_ids,
            permissions=normalized.permissions,
            access_reason=access_reason,
        )


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    principal_id: str
    principal_type: PrincipalType
    token_id: str
    issuer: str
    audience: str
    scopes: ActorScopes
    issued_at: datetime
    expires_at: datetime


class AccessTokenError(PermissionError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class TokenRevocationStore(Protocol):
    def is_revoked(self, token_id: str) -> bool: ...
    def revoke(self, *, token_id: str, expires_at: datetime, reason: str, at: datetime) -> None: ...


class InMemoryTokenRevocationStore:
    def __init__(self) -> None:
        self._revoked: dict[str, tuple[datetime, str]] = {}

    def is_revoked(self, token_id: str) -> bool:
        return token_id in self._revoked

    def revoke(
        self, *, token_id: str, expires_at: datetime, reason: str, at: datetime
    ) -> None:
        if not reason.strip():
            raise ValueError("token revocation reason is required")
        prior = self._revoked.get(token_id)
        material = (expires_at, reason.strip().upper())
        if prior is not None and prior != material:
            raise RuntimeError("token revocation conflict")
        self._revoked[token_id] = material


class AccessTokenService:
    def __init__(
        self,
        *,
        keys: SigningKeyProvider,
        issuer: str,
        audience: str = "railone-api",
        revocations: TokenRevocationStore | None = None,
        max_ttl_seconds: int = 900,
        clock_skew_seconds: int = 30,
    ) -> None:
        if not issuer.strip() or not audience.strip():
            raise ValueError("token issuer and audience are required")
        if not 60 <= max_ttl_seconds <= 3600:
            raise ValueError("maximum token TTL must be between 60 and 3600 seconds")
        self._keys = keys
        self._issuer = issuer.strip()
        self._audience = audience.strip()
        self._revocations = revocations or InMemoryTokenRevocationStore()
        self._max_ttl_seconds = max_ttl_seconds
        self._clock_skew_seconds = clock_skew_seconds

    def issue(
        self,
        *,
        principal_id: str,
        principal_type: PrincipalType,
        scopes: ActorScopes,
        key_id: str,
        ttl_seconds: int = 900,
        token_id: str | None = None,
        at: datetime | None = None,
    ) -> str:
        instant = _instant(at)
        if not isinstance(principal_id, str) or not principal_id.strip():
            raise ValueError("principal_id is required")
        if not isinstance(principal_type, PrincipalType):
            raise TypeError("principal_type must be a PrincipalType")
        if isinstance(ttl_seconds, bool) or not 60 <= ttl_seconds <= self._max_ttl_seconds:
            raise ValueError("token TTL exceeds policy")
        record = self._keys.get_key_record(key_id)
        if record is None:
            raise KeyError(f"unknown access-token signing key: {key_id}")
        if record.purpose is not KeyPurpose.ACCESS_TOKEN_SIGNING:
            raise PermissionError("key is not authorized for access-token signing")
        if not record.permits_signing_at(instant):
            raise PermissionError("access-token signing key is not active")
        normalized = scopes.normalized()
        _validate_principal_scope(principal_type, normalized)
        jti = token_id or f"AT-{uuid4().hex.upper()}"
        expires = instant + timedelta(seconds=ttl_seconds)
        if expires > record.not_after:
            raise ValueError("access token cannot outlive its signing key")
        header = {"alg": "EdDSA", "kid": key_id, "typ": "JWT"}
        claims = {
            "iss": self._issuer, "aud": self._audience,
            "sub": principal_id.strip(), "jti": jti,
            "principal_type": principal_type.value,
            "iat": int(instant.timestamp()), "nbf": int(instant.timestamp()),
            "exp": int(expires.timestamp()),
            "scope": {
                "continuity_uid": normalized.continuity_uid,
                "merchant_ids": list(normalized.merchant_ids),
                "branch_ids": list(normalized.branch_ids),
                "partner_ids": list(normalized.partner_ids),
                "permissions": list(normalized.permissions),
            },
        }
        signing_input = _b64encode(_json(header)) + "." + _b64encode(_json(claims))
        signature = self._keys.sign(key_id, signing_input.encode("ascii"))
        return signing_input + "." + _b64encode(signature)

    def verify(self, token: str, *, at: datetime | None = None) -> AuthenticatedPrincipal:
        instant = _instant(at)
        if not isinstance(token, str) or not token.strip():
            raise AccessTokenError("BEARER_TOKEN_REQUIRED")
        if len(token) > 16_384:
            raise AccessTokenError("TOKEN_TOO_LARGE")
        try:
            encoded_header, encoded_claims, encoded_signature = token.split(".")
            header = json.loads(_b64decode(encoded_header))
            claims = json.loads(_b64decode(encoded_claims))
        except Exception as exc:
            raise AccessTokenError("TOKEN_MALFORMED") from exc
        if not isinstance(header, Mapping) or not isinstance(claims, Mapping):
            raise AccessTokenError("TOKEN_MALFORMED")
        if set(header) != {"alg", "kid", "typ"}:
            raise AccessTokenError("TOKEN_HEADER_INVALID")
        if header.get("alg") != "EdDSA" or header.get("typ") != "JWT":
            raise AccessTokenError("TOKEN_ALGORITHM_REJECTED")
        key_id = header.get("kid")
        record = self._keys.get_key_record(key_id) if isinstance(key_id, str) else None
        if record is None:
            raise AccessTokenError("TOKEN_KEY_NOT_FOUND")
        if record.purpose is not KeyPurpose.ACCESS_TOKEN_SIGNING:
            raise AccessTokenError("TOKEN_KEY_PURPOSE_MISMATCH")
        if record.status is KeyStatus.REVOKED:
            raise AccessTokenError("TOKEN_KEY_REVOKED")
        try:
            Ed25519PublicKey.from_public_bytes(record.public_key).verify(
                _b64decode(encoded_signature),
                f"{encoded_header}.{encoded_claims}".encode("ascii"),
            )
        except (InvalidSignature, ValueError) as exc:
            raise AccessTokenError("TOKEN_SIGNATURE_INVALID") from exc
        if claims.get("iss") != self._issuer or claims.get("aud") != self._audience:
            raise AccessTokenError("TOKEN_ISSUER_OR_AUDIENCE_INVALID")
        try:
            issued_at = _epoch_claim(claims, "iat")
            not_before = _epoch_claim(claims, "nbf")
            expires_at = _epoch_claim(claims, "exp")
            principal_id = claims["sub"]
            token_id = claims["jti"]
            if not isinstance(principal_id, str) or not isinstance(token_id, str):
                raise ValueError("sub and jti must be strings")
            principal_type = PrincipalType(claims["principal_type"])
            raw_scope = claims["scope"]
            if not isinstance(raw_scope, Mapping):
                raise ValueError("scope must be an object")
            for list_name in ("merchant_ids", "branch_ids", "partner_ids", "permissions"):
                raw_values = raw_scope.get(list_name, ())
                if not isinstance(raw_values, list | tuple):
                    raise ValueError(f"{list_name} must be an array")
            scopes = ActorScopes(
                continuity_uid=raw_scope.get("continuity_uid"),
                merchant_ids=tuple(raw_scope.get("merchant_ids", ())),
                branch_ids=tuple(raw_scope.get("branch_ids", ())),
                partner_ids=tuple(raw_scope.get("partner_ids", ())),
                permissions=tuple(raw_scope.get("permissions", ())),
            ).normalized()
            _validate_principal_scope(principal_type, scopes)
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise AccessTokenError("TOKEN_CLAIMS_INVALID") from exc
        skew = timedelta(seconds=self._clock_skew_seconds)
        if issued_at - skew > instant or not_before - skew > instant:
            raise AccessTokenError("TOKEN_NOT_YET_VALID")
        if instant >= expires_at + skew:
            raise AccessTokenError("TOKEN_EXPIRED")
        if expires_at <= issued_at or expires_at - issued_at > timedelta(seconds=self._max_ttl_seconds):
            raise AccessTokenError("TOKEN_LIFETIME_INVALID")
        if not record.not_before <= issued_at < record.not_after or expires_at > record.not_after:
            raise AccessTokenError("TOKEN_OUTSIDE_KEY_LIFETIME")
        if not principal_id.strip() or not token_id.strip():
            raise AccessTokenError("TOKEN_CLAIMS_INVALID")
        if self._revocations.is_revoked(token_id):
            raise AccessTokenError("TOKEN_REVOKED")
        return AuthenticatedPrincipal(
            principal_id=principal_id, principal_type=principal_type,
            token_id=token_id, issuer=self._issuer, audience=self._audience,
            scopes=scopes, issued_at=issued_at, expires_at=expires_at,
        )

    def revoke(
        self,
        *,
        token: str,
        reason: str,
        at: datetime | None = None,
    ) -> None:
        instant = _instant(at)
        principal = self.verify(token, at=instant)
        self._revocations.revoke(
            token_id=principal.token_id,
            expires_at=principal.expires_at,
            reason=reason,
            at=instant,
        )
