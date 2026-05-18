# ==============================
# execution/event_models.py
# RailOne Execution Event Models
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
# EXECUTION EVENTS
# ==========================================
class ExecutionEvent(Base):

    __tablename__ = "execution_events"

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

    event_type = Column(
        String,
        nullable=False
    )

    previous_state = Column(
        String,
        nullable=True
    )

    new_state = Column(
        String,
        nullable=True
    )

    replay_generation = Column(
        Integer,
        default=0
    )

    payload = Column(
        JSON,
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
    "idx_execution_tx_state",
    ExecutionEvent.tx_id,
    ExecutionEvent.new_state
)

Index(
    "idx_execution_continuity",
    ExecutionEvent.continuity_id
)