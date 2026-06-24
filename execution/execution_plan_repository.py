# ==========================================
# execution/execution_plan_repository.py
# ==========================================

from uuid import uuid4
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    JSON,
    Integer,
    DateTime
)

from ledger.db import (
    Base,
    SessionLocal
)


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
        index=True
    )

    routes = Column(
        JSON,
        nullable=False
    )

    max_attempts = Column(
        Integer,
        nullable=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


def save_execution_plan(
    plan
):

    session = SessionLocal()

    try:

        record = ExecutionPlanRecord(

            utt_id=plan.utt_id,

            routes=plan.routes,

            max_attempts=
                plan.max_attempts
        )

        session.add(record)

        session.commit()

    finally:

        session.close()