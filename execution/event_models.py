# ==============================
# execution/event_models.py
# RailOne Execution Continuity Events
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
# EXECUTION EVENT
# Canonical execution lineage event
# ==========================================
class ExecutionEvent(Base):

    __tablename__ = "execution_events"

    # --------------------------------
    # PRIMARY EVENT IDENTITY
    # --------------------------------
    id = Column(

        String,

        primary_key=True,

        default=lambda: str(uuid4())
    )

    # --------------------------------
    # EXECUTION CONTINUITY
    # UTT = canonical execution thread
    # --------------------------------
    utt_id = Column(

        String,

        nullable=False,

        index=True
    )

    # --------------------------------
    # ROUTE REALIZATION
    # RTT = route execution branch
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
    # EXECUTION EVENT TYPE
    # --------------------------------
    event_type = Column(

        String,

        nullable=False
    )

    # --------------------------------
    # STATE TRANSITION
    # --------------------------------
    previous_state = Column(

        String,

        nullable=True
    )

    new_state = Column(

        String,

        nullable=True
    )

    # --------------------------------
    # EXECUTION LINEAGE
    # Enables replay reconstruction
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
    # EXECUTION PAYLOAD
    # --------------------------------
    payload = Column(

        JSON,

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

# UTT continuity tracing
Index(
    "idx_execution_utt",
    ExecutionEvent.utt_id
)

# RTT route tracing
Index(
    "idx_execution_rtt",
    ExecutionEvent.rtt_id
)

# Execution state tracing
Index(
    "idx_execution_state",
    ExecutionEvent.new_state
)

# Identity continuity tracing
Index(
    "idx_execution_continuity",
    ExecutionEvent.continuity_uid
)

# Replay lineage reconstruction
Index(
    "idx_execution_lineage",
    ExecutionEvent.lineage_parent,
    ExecutionEvent.replay_generation
)

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

canonical_state = Column(
    String,
    nullable=True,
    index=True
)

replay_safe_hash = Column(
    String,
    nullable=True,
    index=True
)