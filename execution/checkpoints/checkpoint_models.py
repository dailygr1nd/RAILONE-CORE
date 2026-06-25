# ==============================
# execution/checkpoint_models.py
# RailOne Execution Continuity
# Replay Checkpoints
# ==============================

from sqlalchemy import (

    Column,
    String,
    Integer,
    JSON,
    DateTime,
    Index
)

from datetime import datetime
from uuid import uuid4

from ledger.db import Base


# ==========================================
# EXECUTION CHECKPOINT
# ==========================================
class ExecutionCheckpoint(Base):

    __tablename__ = (
        "execution_checkpoints"
    )

    id = Column(

        String,

        primary_key=True,

        default=lambda:
            str(uuid4())
    )

    # --------------------------------
    # EXECUTION CONTINUITY
    # --------------------------------
    utt_id = Column(

        String,

        nullable=False,

        index=True
    )

    # --------------------------------
    # ROUTE REALIZATION
    # --------------------------------
    rtt_id = Column(

        String,

        nullable=True,

        index=True
    )

    # --------------------------------
    # IDENTITY CONTINUITY
    # --------------------------------
    continuity_uid = Column(

        String,

        nullable=True,

        index=True
    )

    # --------------------------------
    # CHECKPOINT STATE
    # --------------------------------
    checkpoint_state = Column(

        String,

        nullable=False
    )

    # --------------------------------
    # REPLAY LINEAGE
    # --------------------------------
    lineage_parent = Column(

        String,

        nullable=True,

        index=True
    )

    replay_generation = Column(

        Integer,

        default=0
    )

    # --------------------------------
    # SNAPSHOT STATE
    # --------------------------------
    execution_snapshot = Column(

        JSON,

        nullable=True
    )

    provider = Column(
    String,
    nullable=True
    )

    provider_reference = Column(
    String,
    nullable=True
    )

    # --------------------------------
    # SNAPSHOT INTEGRITY
    # --------------------------------
    integrity_hash = Column(

        String,

        nullable=True
    )

    # --------------------------------
    # TIMESTAMP
    # --------------------------------
    created_at = Column(

        DateTime,

        default=datetime.utcnow,

        index=True
    )


# ==========================================
# INDEXES
# ==========================================

Index(
    "idx_checkpoint_utt",
    ExecutionCheckpoint.utt_id
)

Index(
    "idx_checkpoint_rtt",
    ExecutionCheckpoint.rtt_id
)

Index(
    "idx_checkpoint_continuity",
    ExecutionCheckpoint.continuity_uid
)

Index(
    "idx_checkpoint_lineage",
    ExecutionCheckpoint.lineage_parent,
    ExecutionCheckpoint.replay_generation
)