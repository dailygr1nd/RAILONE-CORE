"""R1-IOS-001 institutional legal-identity admission, separate from adapter capability.

Only a trusted RailOne onboarding verifier may sign the compliance decision.
Registration and verification NEVER activate a partner, adapter, or payment rail.
"""

from __future__ import annotations

import base64
import hashlib
import re
import secrets
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from threading import RLock
from typing import Protocol

from railone_crypto.canonical_json import canonical_json_bytes
from railone_crypto.signature_service import ArtifactType, SignatureEnvelope, SignatureService


class InstitutionClass(StrEnum):
    BNK = "BNK"
    MNO = "MNO"
    PSP = "PSP"
    AGG = "AGG"
    SWI = "SWI"
    EMI = "EMI"


class IdentityAdmissionState(StrEnum):
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    VERIFIED = "VERIFIED"


_ID = re.compile(r"INST-([A-Z]{2})-(BNK|MNO|PSP|AGG|SWI|EMI)-([A-Z2-7]{16})\Z")
_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{1,127}\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_MAX_ATTESTATION_AGE = timedelta(days=366)


def _instant(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("institution onboarding time must be timezone-aware")
    return value.astimezone(timezone.utc)


def _name(field: str, value: str) -> str:
    if not isinstance(value, str) or not 2 <= len(value.strip()) <= 160:
        raise ValueError(f"{field} must contain 2 to 160 characters")
    if any(ord(ch) < 32 for ch in value):
        raise ValueError(f"{field} contains invalid characters")
    return value.strip()


def _ref(field: str, value: str) -> str:
    if not isinstance(value, str) or not _REF.fullmatch(value):
        raise ValueError(f"{field} must be an opaque reference (2-128 safe characters)")
    return value


@dataclass(frozen=True, slots=True)
class InstitutionApplication:
    """Untrusted claims submitted for verification; no network permissions."""

    legal_name: str
    display_name: str
    institution_class: InstitutionClass
    home_jurisdiction: str
    registration_reference: str
    regulatory_evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "legal_name", _name("legal_name", self.legal_name))
        object.__setattr__(self, "display_name", _name("display_name", self.display_name))
        if not isinstance(self.institution_class, InstitutionClass):
            raise ValueError("invalid institution class")
        if not isinstance(self.home_jurisdiction, str) or not re.fullmatch(r"[A-Z]{2}", self.home_jurisdiction):
            raise ValueError("home_jurisdiction must be an uppercase ISO 3166-1 alpha-2 code")
        _ref("registration_reference", self.registration_reference)
        if not isinstance(self.regulatory_evidence_refs, tuple) or not 1 <= len(self.regulatory_evidence_refs) <= 20:
            raise ValueError("at least one opaque regulatory evidence reference is required")
        for value in self.regulatory_evidence_refs:
            _ref("regulatory_evidence_ref", value)
        if len(set(self.regulatory_evidence_refs)) != len(self.regulatory_evidence_refs):
            raise ValueError("duplicate regulatory evidence reference")

    def to_payload(self) -> dict[str, object]:
        return {
            "legal_name": self.legal_name,
            "display_name": self.display_name,
            "institution_class": self.institution_class.value,
            "home_jurisdiction": self.home_jurisdiction,
            "registration_reference": self.registration_reference,
            "regulatory_evidence_refs": list(self.regulatory_evidence_refs),
        }

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(canonical_json_bytes(self.to_payload())).hexdigest()


@dataclass(frozen=True, slots=True)
class InstitutionIdentityRecord:
    institution_id: str
    application: InstitutionApplication
    status: IdentityAdmissionState
    submitted_at: datetime
    signed_verification: SignatureEnvelope | None = None
    verified_at: datetime | None = None

    def __post_init__(self) -> None:
        match = _ID.fullmatch(self.institution_id)
        if (match is None or match.group(1) != self.application.home_jurisdiction
                or match.group(2) != self.application.institution_class.value):
            raise ValueError("institution ID does not match immutable registration provenance")
        _instant(self.submitted_at)
        if not isinstance(self.status, IdentityAdmissionState):
            raise ValueError("invalid institutional identity state")
        if self.status is IdentityAdmissionState.VERIFIED:
            if self.signed_verification is None or self.verified_at is None:
                raise ValueError("verified institutional identity requires signed evidence")
            _instant(self.verified_at)
        elif self.signed_verification is not None or self.verified_at is not None:
            raise ValueError("unverified institution cannot carry trusted verification")


class InstitutionIdentityRepository(Protocol):
    def insert(self, record: InstitutionIdentityRecord) -> None: ...
    def get(self, institution_id: str) -> InstitutionIdentityRecord | None: ...
    def find_registration(self, jurisdiction: str, registration_reference: str) -> InstitutionIdentityRecord | None: ...
    def record_verification(self, institution_id: str, evidence: SignatureEnvelope, verified_at: datetime) -> InstitutionIdentityRecord: ...


class InMemoryInstitutionIdentityRepository:
    """Concurrency-safe test repository. No privileges for monetary execution."""

    def __init__(self) -> None:
        self._records: dict[str, InstitutionIdentityRecord] = {}
        self._registration_index: dict[tuple[str, str], str] = {}
        self._lock = RLock()

    def insert(self, record: InstitutionIdentityRecord) -> None:
        if record.status is not IdentityAdmissionState.PENDING_VERIFICATION:
            raise PermissionError("new institution must be pending verification")
        natural_key = (record.application.home_jurisdiction, record.application.registration_reference)
        with self._lock:
            if record.institution_id in self._records or natural_key in self._registration_index:
                raise ValueError("institutional identity already registered")
            self._records[record.institution_id] = record
            self._registration_index[natural_key] = record.institution_id

    def get(self, institution_id: str) -> InstitutionIdentityRecord | None:
        with self._lock:
            return self._records.get(institution_id)

    def find_registration(self, jurisdiction: str, registration_reference: str) -> InstitutionIdentityRecord | None:
        with self._lock:
            institution_id = self._registration_index.get((jurisdiction, registration_reference))
            return self._records.get(institution_id) if institution_id else None

    def record_verification(self, institution_id: str, evidence: SignatureEnvelope, verified_at: datetime) -> InstitutionIdentityRecord:
        with self._lock:
            current = self._records.get(institution_id)
            if current is None:
                raise LookupError("institutional identity not found")
            if current.status is not IdentityAdmissionState.PENDING_VERIFICATION:
                raise PermissionError("institutional verification has already been recorded")
            updated = replace(current, status=IdentityAdmissionState.VERIFIED,
                              signed_verification=evidence, verified_at=_instant(verified_at))
            self._records[institution_id] = updated
            return updated


class InstitutionOnboardingService:
    """Register identity claims; accept only independently signed RailOne decisions.

    A VERIFIED record is not an ACTIVE PartnerInstitution and grants no adapter,
    account-verification, customer-discovery or dispatch permission.
    """

    def __init__(self, *, repository: InstitutionIdentityRepository,
                 signatures: SignatureService, trusted_verifier: str = "RAILONE") -> None:
        if not trusted_verifier or not isinstance(trusted_verifier, str):
            raise ValueError("trusted_verifier is required")
        self._repository = repository
        self._signatures = signatures
        self._trusted_verifier = trusted_verifier

    def register(self, application: InstitutionApplication, *, at: datetime | None = None) -> InstitutionIdentityRecord:
        if not isinstance(application, InstitutionApplication):
            raise TypeError("registration requires InstitutionApplication")
        instant = _instant(at or datetime.now(timezone.utc))
        if self._repository.find_registration(application.home_jurisdiction, application.registration_reference):
            raise ValueError("institutional legal registration already exists")
        suffix = base64.b32encode(secrets.token_bytes(10)).decode("ascii").rstrip("=")
        institution_id = f"INST-{application.home_jurisdiction}-{application.institution_class.value}-{suffix}"
        record = InstitutionIdentityRecord(institution_id, application,
                                           IdentityAdmissionState.PENDING_VERIFICATION, instant)
        self._repository.insert(record)
        return record

    def verify(self, institution_id: str, signed_decision: SignatureEnvelope, *,
               at: datetime | None = None) -> InstitutionIdentityRecord:
        instant = _instant(at or datetime.now(timezone.utc))
        record = self._repository.get(institution_id)
        if record is None:
            raise LookupError("institutional identity not found")
        if record.status is not IdentityAdmissionState.PENDING_VERIFICATION:
            raise PermissionError("institution is not awaiting verification")
        self._check_decision(record, signed_decision, instant)
        return self._repository.record_verification(institution_id, signed_decision, instant)

    def require_verified(self, institution_id: str, *, at: datetime | None = None) -> InstitutionIdentityRecord:
        instant = _instant(at or datetime.now(timezone.utc))
        record = self._repository.get(institution_id)
        if record is None:
            raise LookupError("institutional identity not found")
        if record.status is not IdentityAdmissionState.VERIFIED or record.signed_verification is None:
            raise PermissionError("institutional legal identity is unverified")
        self._check_decision(record, record.signed_verification, instant)
        return record

    def _check_decision(self, record: InstitutionIdentityRecord,
                        signed: SignatureEnvelope, at: datetime) -> None:
        if not isinstance(signed, SignatureEnvelope):
            raise PermissionError("signed institutional decision is required")
        verification = self._signatures.verify_artifact(
            signed, expected_artifact_type=ArtifactType.INSTITUTION_ONBOARDING_ATTESTATION)
        if not verification.valid or signed.protected.get("iss") != self._trusted_verifier:
            raise PermissionError("institutional verification signer is untrusted")
        body = signed.payload
        required = {"version", "institution_id", "application_sha256", "decision",
                    "evidence_ref", "evidence_sha256", "expires_at"}
        if (set(body) != required or type(body.get("version")) is not int or body["version"] != 1
                or body.get("institution_id") != record.institution_id
                or body.get("application_sha256") != record.application.fingerprint
                or body.get("decision") != "LEGAL_AND_REGULATORY_VERIFIED"
                or not isinstance(body.get("evidence_sha256"), str)
                or not _HEX.fullmatch(body["evidence_sha256"])):
            raise PermissionError("institutional decision does not bind to application")
        try:
            _ref("evidence_ref", body.get("evidence_ref"))
        except ValueError:
            raise PermissionError("invalid institutional evidence reference") from None
        issued = signed.protected.get("iat")
        expires = body.get("expires_at")
        if (type(issued) is not int or type(expires) is not int
                or issued < int(record.submitted_at.timestamp())
                or not issued <= int(at.timestamp()) < expires
                or expires - issued > int(_MAX_ATTESTATION_AGE.total_seconds())):
            raise PermissionError("institutional decision expired or predates registration")
