# ==========================================
# execution/route_decision_models.py
# ==========================================

from uuid import uuid4
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Float,
    JSON,
    DateTime
)

from ledger.db import Base


class RouteDecision(Base):

    __tablename__ = "route_decisions"

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
        nullable=True,
        index=True
    )

    rail = Column(
        String,
        nullable=False
    )

    score = Column(
        Float,
        nullable=False
    )

    rank_position = Column(
        String,
        nullable=False
    )

    rationale = Column(
        JSON,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )