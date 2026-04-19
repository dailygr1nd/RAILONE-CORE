from sqlalchemy import Column, String, Float, DateTime
from datetime import datetime
import uuid

from .db import Base

def generate_id():
    return str(uuid.uuid4())


class Account(Base):
    __tablename__ = "accounts"

    id = Column(String, primary_key=True, default=generate_id)
    provider = Column(String)
    currency = Column(String)
    balance = Column(Float, default=0.0)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, default=generate_id)
    sender_id = Column(String)
    receiver_id = Column(String)
    amount = Column(Float)
    currency = Column(String)

    status = Column(String, default="INITIATED")
    idempotency_key = Column(String, unique=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id = Column(String, primary_key=True, default=generate_id)
    tx_id = Column(String)

    account_id = Column(String)
    debit = Column(Float, default=0.0)
    credit = Column(Float, default=0.0)

    currency = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)