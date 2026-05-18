# ==============================
# event_store.py
# RailOne Execution Event Store
# ==============================

from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    JSON,
    Index
)

from datetime import datetime, timezone

from db import Base


class ExecutionEvent(Base):

    __tablename__ = "execution_events"

    # --------------------------------
    # PRIMARY KEY
    # --------------------------------
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    # --------------------------------
    # CONTINUITY REFERENCES
    # --------------------------------
    tx_id = Column(
        String,
        nullable=False
    )

    continuity_id = Column(
        String,
        nullable=False
    )

    lineage_parent = Column(String)

    replay_generation = Column(
        Integer,
        default=0,
        nullable=False
    )

    # --------------------------------
    # EVENT DETAILS
    # --------------------------------
    event_type = Column(
        String,
        nullable=False
    )

    previous_state = Column(String)

    new_state = Column(String)

    payload = Column(
        JSON,
        default=dict
    )

    # --------------------------------
    # TIMESTAMP
    # --------------------------------
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: (
            datetime.now(timezone.utc)
        ),
        nullable=False
    )

    # --------------------------------
    # INDEXES
    # --------------------------------
    __table_args__ = (

        # Replay reconstruction
        Index(
            "idx_execution_events_continuity",
            "continuity_id"
        ),

        # Transaction lookup
        Index(
            "idx_execution_events_tx",
            "tx_id"
        ),

        # Event filtering
        Index(
            "idx_execution_events_type",
            "event_type"
        ),

        # Ordered replay reconstruction
        Index(
            "idx_execution_events_created",
            "created_at"
        ),

        # Replay lineage scans
        Index(
            "idx_execution_events_replay_generation",
            "replay_generation"
        ),
    )