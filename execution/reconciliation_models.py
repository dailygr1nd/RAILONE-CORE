# ==========================================
# execution/reconciliation_models.py
# ==========================================

from uuid import uuid4
from datetime import datetime

from sqlalchemy import (

    Column,
    String,
    Boolean,
    DateTime
)

from ledger.db import Base


class ReconciliationRecord(Base):

    __tablename__ = (
        "reconciliation_records"
    )

    id = Column(

        String,

        primary_key=True,

        default=lambda:
            str(uuid4())
    )

    utt_id = Column(
        String,
        index=True
    )

    rtt_id = Column(
        String,
        index=True
    )

    provider = Column(
        String
    )

    provider_reference = Column(
        String,
        index=True
    )

    reconciled = Column(
        Boolean,
        default=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )