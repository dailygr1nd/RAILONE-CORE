# ==============================
# execution/route_attempt_models.py
# RailOne Route Attempt Persistence
# ==============================

from sqlalchemy import (
    Column,
    String,
    Integer,
    JSON,
    DateTime
)

from datetime import datetime
from uuid import uuid4

from ledger.db import Base


class RouteAttempt(Base):

    __tablename__ = "route_attempts"

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid4())
    )

    utt_id = Column(
        String,
        nullable=False,
        index=True
    )

    rtt_id = Column(
        String,
        nullable=False,
        unique=True,
        index=True
    )

    continuity_uid = Column(
        String,
        nullable=True,
        index=True
    )

    attempt_number = Column(
        Integer,
        nullable=False
    )

    route = Column(
        JSON,
        nullable=False
    )

    status = Column(
        String,
        default="CREATED"
    )

    failure_reason = Column(
        String,
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

    provider_response = Column(
        JSON,
        nullable=True
    )

    latency_ms = Column(
        Integer,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    completed_at = Column(
        DateTime,
        nullable=True
    )