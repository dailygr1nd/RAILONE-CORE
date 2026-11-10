"""RailOne canonical institution wrapper (v0.16 Alpha Phase 3).

This module authenticates an *instruction description*, not permission to move
money. The current execution coordinator, economic-effect guard, and certified
provider boundary remain authoritative. No caller can obtain a dispatch permit
by setting a field in this wrapper.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from railone_crypto.canonical_json import canonical_json_bytes
from railone_crypto.signature_service import ArtifactType, SignatureEnvelope, SignatureService

_VERSION = "1.0.0"
_DOMAIN = b"RAILONE:INSTITUTION-DISPATCH-WRAPPER:V1\x00"
_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_CURRENCY = re.compile(r"^[A-Z]{3}$")
_OPAQUE = re.compile(r"^(?:acctbind|binding|vaultref)[_-][A-Za-z0-9._:-]{3,127}$")
_ADAPTER = re.compile(r"^[A-Za-z0-9._:-]+@[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$")
_RESTRICTED_NAMES = ("msisdn", "account_number", "account_iban", "account_name", "phone_number", "raw_account", "raw_sender", "raw_receiver", "private_key", "access_token", "secret")

_FIELDS: dict[str, tuple[str, ...]] = {
    "trace_identifiers": ("utt_id", "plan_id", "rtt_id", "correlation_id", "attempt_number", "replay_generation"),
    "bilateral_trust_anchors": ("utt_payload_digest", "rtt_birth_digest", "etk_s_digest", "etk_r_digest", "sender_cont_uid", "recipient_cont_uid"),
    "commercial_terms": ("source_amount_minor", "source_currency", "receive_amount_minor", "receive_currency", "pricing_model", "custody_model"),
    "execution_binding": ("route_id", "adapter_binding_ref", "adapter_manifest_digest", "route_decision_digest", "idempotency_key", "request_sha256", "provider_id"),
    "fencing_controls": ("operational_mode", "economic_effect_fence_epoch", "dispatch_guard_decision", "release_evidence_ref"),
    "protected_account_bindings": ("payer_binding_ref", "beneficiary_binding_ref", "source_routing_node", "destination_routing_node"),
}
_ROOT_FIELDS = ("schema_version", "message_type", "envelope_id", "issued_at_epoch", "expires_at_epoch", *_FIELDS)


def _exact_keys(name: str, value: object, required: tuple[str, ...]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != set(required):
        raise ValueError(f"{name}: fields do not match the exact canonical schema")
    return value


def _text(name: str, value: object, pattern: re.Pattern[str] = _ID) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError(f"{name} is not a valid bounded identifier")
    return value


def _integer(name: str, value: object, minimum: int, maximum: int = (1 << 63) - 1) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name} is not an integer within the supported range")
    return value


def _sha(name: str, value: object) -> str:
    return _text(name, value, _DIGEST)


def _inspect_sensitive_keys(value: object) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError("wrapper key must be a string")
            if any(fragment in key.lower() for fragment in _RESTRICTED_NAMES):
                raise ValueError("cleartext identity, credentials or account fields are prohibited")
            _inspect_sensitive_keys(child)
    elif isinstance(value, (tuple, list)):
        for item in value:
            _inspect_sensitive_keys(item)


def _check_body(value: object) -> dict[str, Any]:
    obj = _exact_keys("wrapper", value, _ROOT_FIELDS)
    _inspect_sensitive_keys(obj)
    if obj["schema_version"] != _VERSION or obj["message_type"] != "INSTITUTION_EXECUTION_DISPATCH":
        raise ValueError("unsupported canonical wrapper version or message type")
    envelope_id = _text("envelope_id", obj["envelope_id"], re.compile(r"^IW-[A-F0-9]{32}$"))
    issued = _integer("issued_at_epoch", obj["issued_at_epoch"], 1)
    expires = _integer("expires_at_epoch", obj["expires_at_epoch"], 1)
    if not issued < expires <= issued + 60:
        raise ValueError("wrapper must expire within 60 seconds of issuance")

    sections = {name: _exact_keys(name, obj[name], fields) for name, fields in _FIELDS.items()}
    t = sections["trace_identifiers"]
    for key in ("utt_id", "plan_id", "rtt_id", "correlation_id"):
        _text(key, t[key])
    _integer("attempt_number", t["attempt_number"], 1)
    _integer("replay_generation", t["replay_generation"], 0)
    if t["attempt_number"] - 1 != t["replay_generation"]:
        raise ValueError("RTT attempt and replay generation disagree")

    a = sections["bilateral_trust_anchors"]
    for key in ("utt_payload_digest", "rtt_birth_digest", "etk_s_digest", "etk_r_digest"):
        _sha(key, a[key])
    for key in ("sender_cont_uid", "recipient_cont_uid"):
        _text(key, a[key])

    c = sections["commercial_terms"]
    _integer("source_amount_minor", c["source_amount_minor"], 1)
    _integer("receive_amount_minor", c["receive_amount_minor"], 1)
    for key in ("source_currency", "receive_currency"):
        _text(key, c[key], _CURRENCY)
    if c["pricing_model"] != "PER_INTENT" or c["custody_model"] != "NON_CUSTODIAL":
        raise ValueError("wrapper cannot change RailOne pricing or custody semantics")

    b = sections["execution_binding"]
    for key in ("route_id", "idempotency_key", "provider_id"):
        _text(key, b[key])
    _text("adapter_binding_ref", b["adapter_binding_ref"], _ADAPTER)
    for key in ("adapter_manifest_digest", "route_decision_digest", "request_sha256"):
        _sha(key, b[key])

    fence = sections["fencing_controls"]
    if fence["operational_mode"] != "SEQUENTIAL_RECONCILIATION_SAFE":
        raise ValueError("parallel financial-effect dispatch is not authorized in phase 3")
    _integer("economic_effect_fence_epoch", fence["economic_effect_fence_epoch"], 0)
    if fence["dispatch_guard_decision"] != "RELEASED_FOR_THIS_ATTEMPT":
        raise ValueError("wrapper must contain an explicit, bounded admission assertion")
    if fence["release_evidence_ref"] is not None:
        _text("release_evidence_ref", fence["release_evidence_ref"])
    if t["attempt_number"] > 1 and fence["release_evidence_ref"] is None:
        raise ValueError("replay requires a referenced no-effect/reconciliation release")

    bindings = sections["protected_account_bindings"]
    _text("payer_binding_ref", bindings["payer_binding_ref"], _OPAQUE)
    _text("beneficiary_binding_ref", bindings["beneficiary_binding_ref"], _OPAQUE)
    _text("source_routing_node", bindings["source_routing_node"])
    _text("destination_routing_node", bindings["destination_routing_node"])

    canonical = canonical_json_bytes(obj)
    if len(canonical) > 16_384:
        raise ValueError("wrapper exceeds the 16 KiB canonical message limit")
    # The public envelope ID is derived without including itself in the digest input.
    without_id = dict(obj)
    without_id.pop("envelope_id")
    expected_id = "IW-" + hashlib.sha256(_DOMAIN + canonical_json_bytes(without_id)).hexdigest()[:32].upper()
    if not hmac.compare_digest(expected_id, envelope_id):
        raise ValueError("envelope_id does not match its canonical content")
    return json.loads(canonical)


@dataclass(frozen=True, slots=True)
class CanonicalDispatchWrapper:
    """Immutable-by-value wrapper; nested dictionaries are never exposed directly."""

    canonical_body: str
    wrapper_sha256: str

    @classmethod
    def build(cls, *, issued_at_epoch: int, expires_at_epoch: int, **sections: Mapping[str, Any]) -> "CanonicalDispatchWrapper":
        body = {
            "schema_version": _VERSION,
            "message_type": "INSTITUTION_EXECUTION_DISPATCH",
            "issued_at_epoch": issued_at_epoch,
            "expires_at_epoch": expires_at_epoch,
            **sections,
        }
        body["envelope_id"] = "IW-" + hashlib.sha256(_DOMAIN + canonical_json_bytes(body)).hexdigest()[:32].upper()
        return cls.from_payload(body)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "CanonicalDispatchWrapper":
        body = _check_body(payload)
        encoded = canonical_json_bytes(body)
        return cls(encoded.decode("utf-8"), hashlib.sha256(_DOMAIN + encoded).hexdigest())

    def to_payload(self) -> dict[str, Any]:
        result = json.loads(self.canonical_body)
        if not hmac.compare_digest(
            hashlib.sha256(_DOMAIN + canonical_json_bytes(result)).hexdigest(),
            self.wrapper_sha256,
        ):
            raise ValueError("wrapper integrity check failed")
        _check_body(result)
        return result


@dataclass(frozen=True, slots=True)
class SignedDispatchWrapper:
    wrapper: CanonicalDispatchWrapper
    signature: SignatureEnvelope


@dataclass(frozen=True, slots=True)
class AuthoritativeDispatchSnapshot:
    """Expected values independently loaded from trusted core records.

    This structure is not a permit: callers must obtain it from RailOne's
    authenticated UTT, RTT, ExecutionPlan, route-decision and adapter stores.
    A caller-supplied snapshot is NOT sufficient authorization for real funds.
    """

    utt_id: str
    plan_id: str
    rtt_id: str
    attempt_number: int
    replay_generation: int
    correlation_id: str
    utt_payload_digest: str
    rtt_birth_digest: str
    etk_s_digest: str
    etk_r_digest: str
    sender_cont_uid: str
    recipient_cont_uid: str
    adapter_binding_ref: str
    adapter_manifest_digest: str
    route_decision_digest: str
    route_id: str
    provider_id: str
    request_sha256: str
    idempotency_key: str
    source_amount_minor: int
    source_currency: str
    receive_amount_minor: int
    receive_currency: str
    payer_binding_ref: str
    beneficiary_binding_ref: str
    source_routing_node: str
    destination_routing_node: str
    economic_effect_fence_epoch: int
    release_evidence_ref: str | None

    def assert_matches(self, body: Mapping[str, Any]) -> None:
        paths = {
            "utt_id": ("trace_identifiers", "utt_id"),
            "plan_id": ("trace_identifiers", "plan_id"),
            "rtt_id": ("trace_identifiers", "rtt_id"),
            "attempt_number": ("trace_identifiers", "attempt_number"),
            "replay_generation": ("trace_identifiers", "replay_generation"),
            "correlation_id": ("trace_identifiers", "correlation_id"),
            "utt_payload_digest": ("bilateral_trust_anchors", "utt_payload_digest"),
            "rtt_birth_digest": ("bilateral_trust_anchors", "rtt_birth_digest"),
            "etk_s_digest": ("bilateral_trust_anchors", "etk_s_digest"),
            "etk_r_digest": ("bilateral_trust_anchors", "etk_r_digest"),
            "sender_cont_uid": ("bilateral_trust_anchors", "sender_cont_uid"),
            "recipient_cont_uid": ("bilateral_trust_anchors", "recipient_cont_uid"),
            "adapter_binding_ref": ("execution_binding", "adapter_binding_ref"),
            "adapter_manifest_digest": ("execution_binding", "adapter_manifest_digest"),
            "route_decision_digest": ("execution_binding", "route_decision_digest"),
            "route_id": ("execution_binding", "route_id"),
            "provider_id": ("execution_binding", "provider_id"),
            "request_sha256": ("execution_binding", "request_sha256"),
            "idempotency_key": ("execution_binding", "idempotency_key"),
            "source_amount_minor": ("commercial_terms", "source_amount_minor"),
            "source_currency": ("commercial_terms", "source_currency"),
            "receive_amount_minor": ("commercial_terms", "receive_amount_minor"),
            "receive_currency": ("commercial_terms", "receive_currency"),
            "payer_binding_ref": ("protected_account_bindings", "payer_binding_ref"),
            "beneficiary_binding_ref": ("protected_account_bindings", "beneficiary_binding_ref"),
            "source_routing_node": ("protected_account_bindings", "source_routing_node"),
            "destination_routing_node": ("protected_account_bindings", "destination_routing_node"),
            "economic_effect_fence_epoch": ("fencing_controls", "economic_effect_fence_epoch"),
            "release_evidence_ref": ("fencing_controls", "release_evidence_ref"),
        }
        for field_name, (section, item) in paths.items():
            if body[section][item] != getattr(self, field_name):
                raise PermissionError(f"wrapper {field_name} disagrees with authoritative RailOne state")


class DispatchWrapperService:
    """Sign and verify an instruction wrapper; NEVER infer execution permission."""

    def __init__(self, signatures: SignatureService, *, signing_key_id: str, expected_core_owner_id: str = "RAILONE") -> None:
        self._signatures = signatures
        self._signing_key_id = signing_key_id
        self._expected_owner = expected_core_owner_id

    def issue(
        self, wrapper: CanonicalDispatchWrapper, *, expected: AuthoritativeDispatchSnapshot,
        at: datetime,
    ) -> SignedDispatchWrapper:
        instant = _aware(at)
        body = wrapper.to_payload()
        expected.assert_matches(body)
        if not body["issued_at_epoch"] <= int(instant.timestamp()) < body["expires_at_epoch"]:
            raise PermissionError("wrapper is outside its issuance window")
        signed = self._signatures.sign_artifact(
            artifact_type=ArtifactType.INSTITUTION_DISPATCH_WRAPPER,
            payload=body,
            key_id=self._signing_key_id,
            issued_at=instant,
        )
        if signed.protected.get("iss") != self._expected_owner:
            raise PermissionError("wrapper was not signed by RailOne Core")
        return SignedDispatchWrapper(wrapper, signed)

    def verify(
        self, signed: SignedDispatchWrapper, *, expected: AuthoritativeDispatchSnapshot,
        at: datetime,
    ) -> CanonicalDispatchWrapper:
        instant = _aware(at)
        result = self._signatures.verify_artifact(
            signed.signature,
            expected_artifact_type=ArtifactType.INSTITUTION_DISPATCH_WRAPPER,
        )
        if not result.valid:
            raise PermissionError(f"dispatch wrapper signature invalid: {result.reason}")
        if signed.signature.protected.get("iss") != self._expected_owner:
            raise PermissionError("wrapper signer is not the trusted RailOne Core identity")
        payload = signed.wrapper.to_payload()
        if canonical_json_bytes(signed.signature.payload) != canonical_json_bytes(payload):
            raise PermissionError("wrapper differs from signed payload")
        if not payload["issued_at_epoch"] <= int(instant.timestamp()) < payload["expires_at_epoch"]:
            raise PermissionError("dispatch wrapper expired or not yet valid")
        signed_iat = signed.signature.protected["iat"]
        if not payload["issued_at_epoch"] <= signed_iat < payload["expires_at_epoch"]:
            raise PermissionError("signature timestamp disagrees with the wrapper validity")
        expected.assert_matches(payload)
        return signed.wrapper


def _aware(instant: datetime) -> datetime:
    if not isinstance(instant, datetime) or instant.tzinfo is None:
        raise ValueError("verification time must be timezone-aware")
    return instant.astimezone(timezone.utc)
