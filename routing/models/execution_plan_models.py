# ==============================
# routing/execution_plan_models.py
# RailOne Execution Plan Persistence
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


class ExecutionPlanRecord(Base):

    __tablename__ = "execution_plans"

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid4())
    )

    utt_id = Column(
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

    ranked_routes = Column(
        JSON,
        nullable=False
    )

    max_attempts = Column(
        Integer,
        default=5
    )

    attempts_used = Column(
        Integer,
        default=0
    )

    successful_route = Column(
        JSON,
        nullable=True
    )

    failed_routes = Column(
        JSON,
        nullable=True
    )

    status = Column(
        String,
        default="ACTIVE"
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )