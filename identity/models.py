# ==============================
# identity/models.py
# RailOne Identity Continuity Models
# ==============================

from datetime import (
    datetime,
    timezone
)

from sqlalchemy import (

    Column,
    String,
    Integer,
    Float,
    DateTime,
    JSON,
    Index
)

from db import Base


# ==========================================
# USERS
# ==========================================
class User(Base):

    __tablename__ = "users"

    # --------------------------------
    # PUBLIC IDENTITY
    # --------------------------------
    railone_id = Column(
        String,
        primary_key=True
    )

    # --------------------------------
    # CONTINUITY REFERENCES
    # --------------------------------
    continuity_uid = Column(
        String,
        unique=True,
        nullable=True
    )

    rig_id = Column(
        String,
        unique=True,
        nullable=True
    )

    rio_id = Column(
        String,
        unique=True,
        nullable=True
    )

    active_riv_id = Column(
        String,
        nullable=True
    )

    # --------------------------------
    # TRUST CONTEXT
    # --------------------------------
    corridor = Column(
        String,
        nullable=True,
        default="EA"
    )

    trust_tier = Column(
        String,
        nullable=True,
        default="T0"
    )

    revision = Column(
        Integer,
        nullable=True,
        default=1
    )

    # --------------------------------
    # USER DATA
    # --------------------------------
    full_name = Column(String)

    national_id = Column(
        String,
        unique=True,
        nullable=True
    )

    kyc_status = Column(
        String,
        default="PENDING"
    )

    # --------------------------------
    # TIMESTAMPS
    # --------------------------------
    created_at = Column(
        DateTime(timezone=True),
        default=lambda:
            datetime.now(
                timezone.utc
            )
    )

    # --------------------------------
    # INDEXES
    # --------------------------------
    __table_args__ = (

        Index(
            "idx_users_continuity_uid",
            "railone_id"
        ),

        Index(
            "idx_users_rio",
            "rio_id"
        ),
    )


# ==========================================
# RIG OBJECTS
# Immutable Genesis Anchors
# ==========================================
class RIGObject(Base):

    __tablename__ = "rig_objects"

    rig_id = Column(
        String,
        primary_key=True
    )

    continuity_uid = Column(
        String,
        unique=True,
        nullable=True
    )

    genesis_provider = Column(
        String
    )

    genesis_country = Column(
        String
    )

    genesis_hash = Column(
        String
    )

    genesis_attestation = Column(
        JSON,
        default=dict
    )

    created_at = Column(
        DateTime(timezone=True),

        default=lambda:
            datetime.now(
                timezone.utc
            )
    )

    __table_args__ = (

        Index(
            "idx_rig_continuity_uid",
            "railone_id"
        ),
    )


# ==========================================
# RIO OBJECTS
# Canonical Identity Continuity Objects
# ==========================================
class RIOObject(Base):

    __tablename__ = "rio_objects"

    rio_id = Column(
        String,
        primary_key=True
    )

    continuity_uid = Column(
        String,
        unique=True,
        nullable=True
    )

    rig_id = Column(
        String,
        nullable=True
    )

    current_riv_id = Column(
        String,
        nullable=True
    )

    trust_tier = Column(
        String,
        nullable=True
    )

    corridor = Column(
        String,
        nullable=True
    )

    identity_state = Column(
        String,
        default="ACTIVE"
    )

    created_at = Column(
        DateTime(timezone=True),

        default=lambda:
            datetime.now(
                timezone.utc
            )
    )

    __table_args__ = (

        Index(
            "idx_rio_continuity_uid",
            "railone_id"
        ),
    )


# ==========================================
# RIV OBJECTS
# Identity Revision Lineage
# ==========================================
class RIVObject(Base):

    __tablename__ = "riv_objects"

    riv_id = Column(
        String,
        primary_key=True
    )

    rio_id = Column(
        String,
        nullable=True
    )

    continuity_uid = Column(
        String,
        nullable=True
    )

    revision = Column(
        Integer,
        nullable=True
    )

    trust_tier = Column(
        String,
        nullable=True
    )

    revision_reason = Column(
        String
    )

    revision_metadata = Column(
        JSON,
        default=dict
    )

    attestation_reference = Column(
        String
    )

    replay_generation = Column(
        Integer,
        default=0
    )

    created_at = Column(
        DateTime(timezone=True),

        default=lambda:
            datetime.now(
                timezone.utc
            )
    )

    __table_args__ = (

        Index(
            "idx_riv_continuity_uid",
            "railone_id"
        ),

        Index(
            "idx_riv_revision",
            "revision"
        ),
    )


# ==========================================
# IDENTITY ATTESTATIONS
# ==========================================
class IdentityAttestation(Base):

    __tablename__ = "identity_attestations"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    continuity_uid = Column(
        String,
        nullable=True
    )

    riv_id = Column(
        String,
        nullable=True
    )

    institution_id = Column(
        String
    )

    attestation_type = Column(
        String
    )

    attestation_hash = Column(
        String
    )

    trust_score = Column(
        Float,
        default=0.0
    )

    attestation_payload = Column(
        JSON,
        default=dict
    )

    created_at = Column(
        DateTime(timezone=True),

        default=lambda:
            datetime.now(
                timezone.utc
            )
    )

    __table_args__ = (

        Index(
            "idx_identity_attestation_uid",
            "railone_id"
        ),
    )


# ==========================================
# IDENTITY REPLAY EVENTS
# ==========================================
class IdentityReplayEvent(Base):

    __tablename__ = "identity_replay_events"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    continuity_uid = Column(
        String,
        nullable=True
    )

    rio_id = Column(
        String
    )

    riv_id = Column(
        String
    )

    event_type = Column(
        String,
        nullable=True
    )

    previous_state = Column(
        String
    )

    new_state = Column(
        String
    )

    payload = Column(
        JSON,
        default=dict
    )

    created_at = Column(
        DateTime(timezone=True),

        default=lambda:
            datetime.now(
                timezone.utc
            )
    )

    __table_args__ = (

        Index(
            "idx_identity_replay_uid",
            "railone_id"
        ),
    )


# ==========================================
# ZK-SD RECORDS
# ==========================================
class ZKSDRecord(Base):

    __tablename__ = "zk_sd_records"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    continuity_uid = Column(
        String,
        nullable=True
    )

    riv_id = Column(
        String
    )

    disclosure_type = Column(
        String
    )

    zk_proof_hash = Column(
        String
    )

    disclosure_scope = Column(
        String
    )

    verifier_reference = Column(
        String
    )

    created_at = Column(
        DateTime(timezone=True),

        default=lambda:
            datetime.now(
                timezone.utc
            )
    )

    __table_args__ = (

        Index(
            "idx_zksd_uid",
            "railone_id"
        ),
    )