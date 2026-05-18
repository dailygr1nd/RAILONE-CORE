# ==============================
# ledger/models.py
# ==============================

from sqlalchemy import Column, String, Float, DateTime
from datetime import datetime

from ledger.db import Base



# --------------------------------
# ACCOUNT MODEL
# --------------------------------
class Account(Base):
    __tablename__ = "accounts"

    id = Column(String, primary_key=True)

    currency = Column(String)
    account_type = Column(String)

    mirrored_available_state = Column(
    Float,
    default=0.0,
    nullable=False
)
    execution_reservation = Column(
    Float,
    default=0.0,
    nullable=False
)

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


    # ==============================
# network_models.py
# ==============================

from sqlalchemy import Column, String, DateTime, ForeignKey
from datetime import datetime
from uuid import uuid4

from ledger.db import Base


# --------------------------------
# INSTITUTIONS (NETWORK PARTICIPANTS)
# --------------------------------
class Institution(Base):
    __tablename__ = "institutions"

    id = Column(String, primary_key=True)  # e.g. PSP_KE, BANK_TZ
    name = Column(String)

    type = Column(String)      # PSP, BANK, WALLET
    country = Column(String)   # KE, TZ, UG

    status = Column(String, default="ACTIVE")  # ACTIVE / INACTIVE

    created_at = Column(DateTime, default=datetime.utcnow)


# --------------------------------
# INSTITUTION KEYS (FOR ATTESTATIONS)
# --------------------------------
class InstitutionKey(Base):
    __tablename__ = "institution_keys"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))

    institution_id = Column(String, ForeignKey("institutions.id"))

    public_key = Column(String)     # used for signature verification
    key_version = Column(String)    # allow rotation

    status = Column(String, default="ACTIVE")  # ACTIVE / REVOKED

    created_at = Column(DateTime, default=datetime.utcnow)


# --------------------------------
# USER ↔ INSTITUTION ACCOUNT LINK
# --------------------------------
class UserAccountLink(Base):
    __tablename__ = "user_account_links"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))

    railone_id = Column(String)        # your internal user ID
    institution_id = Column(String)    # PSP_KE, BANK_TZ

    external_account_ref = Column(String)  # phone number / account number
    currency = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow)


# --------------------------------
# ATTESTATIONS (TRUST EVENTS)
# --------------------------------
class Attestation(Base):
    __tablename__ = "attestations"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))

    tx_id = Column(String)                # transaction reference
    institution_id = Column(String)       # who signed

    attestation_type = Column(String)     # FUNDS_AVAILABLE, SETTLED, etc.
    signature = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow)