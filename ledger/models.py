# ==============================
# ledger/models.py
# ==============================

from sqlalchemy import Column, String, Float, DateTime
from datetime import datetime

from ledger.db import Base


# --------------------------------
# USER MODEL
# --------------------------------
class User(Base):
    __tablename__ = "users"

    railone_id = Column(String, primary_key=True)
    username = Column(String, unique=True, nullable=True)

    national_id = Column(String, index=True)

    kyc_status = Column(String, default="PENDING")
    risk_level = Column(String, default="LOW")

    created_at = Column(DateTime, default=datetime.utcnow)


# --------------------------------
# ACCOUNT MODEL
# --------------------------------
class Account(Base):
    __tablename__ = "accounts"

    id = Column(String, primary_key=True)

    currency = Column(String)
    account_type = Column(String)

    balance = Column(Float, default=0.0)
    locked_balance = Column(Float, default=0.0)

    created_at = Column(DateTime, default=datetime.utcnow)


# --------------------------------
# JOURNAL ENTRY (LEDGER)
# --------------------------------
class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id = Column(String, primary_key=True)

    tx_id = Column(String)
    account_id = Column(String)

    amount = Column(Float)
    entry_type = Column(String)  # DEBIT / CREDIT

    currency = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow)

    # --------------------------------
# TRANSACTION MODEL
# --------------------------------
class Transaction(Base):
    __tablename__ = "transactions"

    tx_id = Column(String, primary_key=True)

    sender_account = Column(String)
    receiver_account = Column(String)

    amount = Column(Float)
    net_amount = Column(Float)

    currency_from = Column(String)
    currency_to = Column(String)

    status = Column(String)
    reason = Column(String, nullable=True)

    fee = Column(Float, default=0.0)
    profit = Column(Float, default=0.0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)