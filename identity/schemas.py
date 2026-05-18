# ==============================
# identity/schemas.py
# RailOne Identity Schemas
# ==============================

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime


# ==========================================
# PUBLIC RAILONE IDENTITY
# ==========================================
class RailOneIdentitySchema(BaseModel):

    railone_id: str

    continuity_uid: str

    rig_id: str

    rio_id: str

    active_riv_id: str

    corridor: str = "EA"

    trust_tier: str = "T0"

    revision: int = 1


# ==========================================
# USER PROFILE
# ==========================================
class UserProfileSchema(BaseModel):

    full_name: Optional[str] = None

    national_id: str

    kyc_status: str = "PENDING"

    created_at: Optional[datetime] = None


# ==========================================
# FULL USER CONTINUITY OBJECT
# ==========================================
class UserContinuitySchema(

    RailOneIdentitySchema,
    UserProfileSchema
):
    pass


# ==========================================
# RIG SCHEMA
# Immutable Genesis Anchor
# ==========================================
class RIGSchema(BaseModel):

    rig_id: str

    continuity_uid: str

    genesis_provider: Optional[str] = None

    genesis_country: Optional[str] = None

    genesis_hash: Optional[str] = None

    genesis_attestation: Dict[str, Any] = Field(
        default_factory=dict
    )

    created_at: Optional[datetime] = None


# ==========================================
# RIO SCHEMA
# Canonical Identity Object
# ==========================================
class RIOSchema(BaseModel):

    rio_id: str

    continuity_uid: str

    rig_id: str

    current_riv_id: str

    trust_tier: str

    corridor: str

    identity_state: str = "ACTIVE"

    created_at: Optional[datetime] = None


# ==========================================
# RIV SCHEMA
# Identity Revision Object
# ==========================================
class RIVSchema(BaseModel):

    riv_id: str

    rio_id: str

    continuity_uid: str

    revision: int

    trust_tier: str

    revision_reason: Optional[str] = None

    revision_metadata: Dict[str, Any] = Field(
        default_factory=dict
    )

    attestation_reference: Optional[str] = None

    replay_generation: int = 0

    created_at: Optional[datetime] = None


# ==========================================
# IDENTITY ATTESTATION
# ==========================================
class IdentityAttestationSchema(BaseModel):

    continuity_uid: str

    riv_id: str

    institution_id: Optional[str] = None

    attestation_type: Optional[str] = None

    attestation_hash: Optional[str] = None

    trust_score: float = 0.0

    attestation_payload: Dict[str, Any] = Field(
        default_factory=dict
    )

    created_at: Optional[datetime] = None


# ==========================================
# IDENTITY REPLAY EVENT
# ==========================================
class IdentityReplayEventSchema(BaseModel):

    continuity_uid: str

    rio_id: Optional[str] = None

    riv_id: Optional[str] = None

    event_type: str

    previous_state: Optional[str] = None

    new_state: Optional[str] = None

    payload: Dict[str, Any] = Field(
        default_factory=dict
    )

    created_at: Optional[datetime] = None


# ==========================================
# ZK-SD RECORD
# ==========================================
class ZKSDRecordSchema(BaseModel):

    continuity_uid: str

    riv_id: Optional[str] = None

    disclosure_type: Optional[str] = None

    zk_proof_hash: Optional[str] = None

    disclosure_scope: Optional[str] = None

    verifier_reference: Optional[str] = None

    created_at: Optional[datetime] = None


# ==========================================
# ONBOARDING REQUEST
# ==========================================
class IdentityOnboardingRequest(BaseModel):

    full_name: str

    national_id: str

    corridor: str = "EA"


# ==========================================
# ONBOARDING RESPONSE
# ==========================================
class IdentityOnboardingResponse(BaseModel):

    success: bool

    identity: UserContinuitySchema

    accounts: List[Dict[str, Any]]

    attestation: Dict[str, Any]


# ==========================================
# TRUST TIER UPDATE
# ==========================================
class TrustTierUpdateSchema(BaseModel):

    continuity_uid: str

    previous_tier: str

    new_tier: str

    revision_reason: str

    institution_id: str


# ==========================================
# RIV EVOLUTION REQUEST
# ==========================================
class RIVEvolutionRequest(BaseModel):

    continuity_uid: str

    revision_reason: str

    metadata: Dict[str, Any] = Field(
        default_factory=dict
    )


# ==========================================
# ZK-SD DISCLOSURE REQUEST
# ==========================================
class ZKDisclosureRequest(BaseModel):

    continuity_uid: str

    disclosure_type: str

    verifier_reference: str

    disclosure_scope: str


# ==========================================
# IDENTITY REPLAY REQUEST
# ==========================================
class IdentityReplayRequest(BaseModel):

    continuity_uid: str

    replay_generation: int = 0


# ==========================================
# CONTINUITY RECONSTRUCTION RESPONSE
# ==========================================
class ContinuityReconstructionResponse(BaseModel):

    continuity_uid: str

    rio: Optional[RIOSchema] = None

    current_riv: Optional[RIVSchema] = None

    attestations: List[
        IdentityAttestationSchema
    ] = Field(default_factory=list)

    replay_events: List[
        IdentityReplayEventSchema
    ] = Field(default_factory=list)

    reconstructed: bool = False