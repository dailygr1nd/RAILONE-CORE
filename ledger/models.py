from sqlalchemy import Column, String, Float, DateTime
from datetime import datetime
import uuid

from .db import Base


def generate_id():
    return str(uuid.uuid4())


class Account(Base):
    __tablename__ = "accounts"

    id = Column(String, primary_key=True, default=generate_id)
    owner_id = Column(String)
    provider = Column(String)
    currency = Column(String)

    # ⚠️ NOT SOURCE OF TRUTH ANYMORE
    balance = Column(Float, default=0.0)   # cached / derived
    reserved = Column(Float, default=0.0)

    account_type = Column(String, default="USER")  # USER / SETTLEMENT / SYSTEM


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True)
    sender_id = Column(String)
    receiver_id = Column(String)

    amount = Column(Float)
    currency = Column(String)

    status = Column(String)
    route = Column(String)
    rail_reference = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow)


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id = Column(String, primary_key=True, default=generate_id)
    tx_id = Column(String)

    account_id = Column(String)
    entry_type = Column(String)  # DEBIT / CREDIT
    amount = Column(Float)
    currency = Column(String, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)