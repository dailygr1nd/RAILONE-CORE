from sqlalchemy import (
    Column,
    String,
    JSON,
    DateTime,
    Integer
)

from datetime import datetime, timezone

from db import Base


class ExecutionEvent(Base):

    __tablename__ = "execution_events"

    id = Column(Integer, primary_key=True)

    tx_id = Column(String, index=True, nullable=False)

    continuity_id = Column(String, index=True)

    event_type = Column(String, nullable=False)

    previous_state = Column(String)

    new_state = Column(String)

    payload = Column(JSON, default={})

    lineage_parent = Column(String)

    replay_generation = Column(Integer, default=0)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )