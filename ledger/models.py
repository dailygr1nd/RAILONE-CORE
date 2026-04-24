# ==============================
# ledger/models.py
# ==============================

from sqlalchemy import Column, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


# --------------------------------
# ACCOUNT TABLE
# --------------------------------
class Account(Base):
    __tablename__ = "accounts"

    id = Column(String, primary_key=True)
    balance = Column(Float, default=0.0)     # total funds
    reserved = Column(Float, default=0.0)    # locked funds

    def available(self):
        return self.balance - self.reserved


# --------------------------------
# JOURNAL (LEDGER)
# --------------------------------
class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id = Column(String, primary_key=True)
    tx_id = Column(String, index=True)

    account_id = Column(String, index=True)

    entry_type = Column(String)  # DEBIT / CREDIT
    amount = Column(Float)
    currency = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow)


# --------------------------------
# TRANSACTIONS (OPTIONAL TRACKING)
# --------------------------------
class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True)
    status = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)