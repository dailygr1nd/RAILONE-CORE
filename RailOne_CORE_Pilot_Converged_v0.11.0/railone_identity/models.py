"""Immutable identity-continuity records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class TrustTier(StrEnum):
    T0 = "T0"
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"
    T4 = "T4"
    T5 = "T5"


class IdentityStatus(StrEnum):
    ACTIVE = "ACTIVE"
    REVERIFICATION_REQUIRED = "REVERIFICATION_REQUIRED"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"


@dataclass(frozen=True, slots=True)
class IdentityGenesis:
    rig_id: str
    continuity_uid: str
    continuity_key_id: str
    identity_fingerprint: str
    verification_provider_id: str
    verification_reference: str
    evidence_sha256: str
    attestation_id: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class IdentityRevision:
    riv_id: str
    rio_id: str
    continuity_uid: str
    revision: int
    trust_tier: TrustTier
    status: IdentityStatus
    reason: str
    attestation_id: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class IdentityObject:
    rio_id: str
    railone_id: str
    continuity_uid: str
    rig_id: str
    active_riv_id: str
    corridor: str
    status: IdentityStatus
    created_at: datetime


@dataclass(frozen=True, slots=True)
class IdentityBundle:
    genesis: IdentityGenesis
    identity: IdentityObject
    active_revision: IdentityRevision
