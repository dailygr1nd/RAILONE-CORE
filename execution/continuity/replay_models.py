# ==========================================
# execution/replay_models.py
# RailOne Replay Persistence Models
# ==========================================

import uuid

from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    ForeignKey,
    JSON,
    Boolean,
    Text
)

from ledger.db import Base


# ==========================================
# EXECUTION REPLAY RECORD
# ==========================================
class ExecutionReplay(Base):

    __tablename__ = "execution_replays"

    # ======================================
    # PRIMARY IDENTITY
    # ======================================
    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    # ======================================
    # CONTINUITY LINKAGE
    # ======================================
    continuity_uid = Column(
        String,
        nullable=False,
        index=True
    )

    utt_id = Column(
        String,
        nullable=False,
        index=True
    )

    previous_utt_id = Column(
        String,
        nullable=True,
        index=True
    )

    # ======================================
    # ROUTE CONTINUITY
    # ======================================
    rtt_id = Column(
        String,
        nullable=True,
        index=True
    )

    previous_rtt_id = Column(
        String,
        nullable=True,
        index=True
    )

    # ======================================
    # REPLAY LINEAGE
    # ======================================
    replay_generation = Column(
        Integer,
        default=0,
        nullable=False
    )

    lineage_parent = Column(
        String,
        nullable=True,
        index=True
    )

    replay_reason = Column(
        String,
        nullable=True
    )

    replay_strategy = Column(
        String,
        nullable=True
    )

    # ======================================
    # PROVIDER CONTINUITY
    # ======================================
    provider = Column(
        String,
        nullable=True,
        index=True
    )

    provider_reference = Column(
        String,
        nullable=True,
        index=True
    )

    # ======================================
    # EXECUTION CONTEXT
    # ======================================
    previous_state = Column(
        String,
        nullable=True
    )

    new_state = Column(
        String,
        nullable=True
    )

    canonical_execution_state = Column(
        String,
        nullable=True
    )

    # ======================================
    # REPLAY SAFETY
    # ======================================
    replay_safe_hash = Column(
        String,
        nullable=True,
        index=True
    )

    replay_integrity_verified = Column(
        Boolean,
        default=False
    )

    divergence_detected = Column(
        Boolean,
        default=False
    )

    divergence_type = Column(
        String,
        nullable=True
    )

    # ======================================
    # RECONSTRUCTION CONTEXT
    # ======================================
    replay_snapshot = Column(
        JSON,
        nullable=True
    )

    checkpoint_snapshot = Column(
        JSON,
        nullable=True
    )

    provider_reconciliation = Column(
        JSON,
        nullable=True
    )

    recovery_metadata = Column(
        JSON,
        nullable=True
    )

    # ======================================
    # EXECUTION NOTES
    # ======================================
    replay_notes = Column(
        Text,
        nullable=True
    )

    # ======================================
    # TIMESTAMPS
    # ======================================
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )