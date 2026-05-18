# ==============================
# execution/checkpoint_models.py
# RailOne Execution Checkpoints
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

from db import Base


# ==========================================
# EXECUTION CHECKPOINTS
# ==========================================
class ExecutionCheckpoint(Base):

    __tablename__ = "execution_checkpoints"

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid4())
    )

    tx_id = Column(
        String,
        nullable=False,
        index=True
    )

    continuity_id = Column(
        String,
        nullable=True,
        index=True
    )

    checkpoint_state = Column(
        String,
        nullable=False
    )

    replay_generation = Column(
        Integer,
        default=0
    )

    execution_snapshot = Column(
        JSON,
        nullable=True
    )

    integrity_hash = Column(
        String,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        index=True
    )


# ==========================================
# INDEXES
# ==========================================
Index(
    "idx_checkpoint_tx",
    ExecutionCheckpoint.tx_id
)

Index(
    "idx_checkpoint_continuity",
    ExecutionCheckpoint.continuity_id
)