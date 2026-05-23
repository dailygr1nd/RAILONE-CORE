# ==============================
# ledger/models.py
# ==============================


from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Float,
    DateTime,
    Integer
)

from ledger.db import Base


# =========================================
# EXECUTION ACCOUNT
# =========================================
class Account(Base):

    __tablename__ = "accounts"

    # --------------------------------
    # ACCOUNT ID
    # --------------------------------
    id = Column(
        String,
        primary_key=True
    )

    # --------------------------------
    # CONTINUITY CONTEXT
    # --------------------------------
    railone_id = Column(
        String,
        nullable=False,
        index=True
    )

    continuity_uid = Column(
        String,
        nullable=False,
        index=True
    )

    # --------------------------------
    # INSTITUTION CONTEXT
    # --------------------------------
    institution_id = Column(
        String,
        nullable=False,
        index=True
    )

    # --------------------------------
    # ACCOUNT STATE
    # --------------------------------
    currency = Column(
        String,
        nullable=False
    )

    account_type = Column(
        String,
        nullable=False
    )

    mirrored_available_state = Column(
        Float,
        default=0.0
    )

    execution_reservation = Column(
        Float,
        default=0.0
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


# =========================================
# EXECUTION THREAD
# Canonical execution continuity object
# =========================================
class ExecutionThread(Base):

    __tablename__ = "execution_threads"

    # --------------------------------
    # CANONICAL EXECUTION CONTINUITY
    # --------------------------------
    utt_id = Column(
        String,
        primary_key=True
    )

    # --------------------------------
    # EXECUTION STATE
    # --------------------------------
    execution_state = Column(
        String,
        nullable=False,
        default="INITIATED"
    )

    settlement_state = Column(
        String,
        nullable=False,
        default="PENDING"
    )

    replay_generation = Column(
        Integer,
        default=0
    )

    current_rtt_id = Column(
        String,
        nullable=True
    )

    # --------------------------------
    # EXECUTION PARTICIPANTS
    # --------------------------------
    sender_account_id = Column(
        String,
        nullable=False
    )

    receiver_account_id = Column(
        String,
        nullable=False
    )

    # --------------------------------
    # VALUE CONTEXT
    # --------------------------------
    currency_from = Column(
        String,
        nullable=False
    )

    currency_to = Column(
        String,
        nullable=False
    )

    gross_amount = Column(
        Float,
        nullable=False
    )

    net_amount = Column(
        Float,
        nullable=False
    )

    fee_amount = Column(
        Float,
        default=0.0
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


# =========================================
# ROUTE EXECUTION THREAD
# RTT realization layer
# =========================================
class RouteExecution(Base):

    __tablename__ = "route_executions"

    rtt_id = Column(
        String,
        primary_key=True
    )

    utt_id = Column(
        String,
        nullable=False,
        index=True
    )

    route_state = Column(
        String,
        nullable=False,
        default="ROUTED"
    )

    route_generation = Column(
        Integer,
        default=1
    )

    institution_path = Column(
        String,
        nullable=True
    )

    execution_attestation = Column(
        String,
        nullable=True
    )

    route_attestation = Column(
        String,
        nullable=True
    )

    settlement_provenance = Column(
        String,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


# =========================================
# JOURNAL ENTRIES
# Accounting truth only
# =========================================
class JournalEntry(Base):

    __tablename__ = "journal_entries"

    id = Column(
        String,
        primary_key=True
    )

    # --------------------------------
    # EXECUTION CONTINUITY
    # --------------------------------
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

    # --------------------------------
    # ACCOUNTING STATE
    # --------------------------------
    account_id = Column(
        String,
        nullable=False
    )

    amount = Column(
        Float,
        nullable=False
    )

    entry_type = Column(
        String,
        nullable=False
    )

    currency = Column(
        String,
        nullable=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    # =========================================
# INSTITUTION
# =========================================
class Institution(Base):

    __tablename__ = "institutions"

    institution_id = Column(
        String,
        primary_key=True
    )

    institution_name = Column(
        String,
        nullable=False
    )

    institution_type = Column(
        String,
        nullable=False
    )

    corridor = Column(
        String,
        nullable=False
    )

    operational_status = Column(
        String,
        default="ACTIVE"
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


# =========================================
# INSTITUTION KEYS
# =========================================
class InstitutionKey(Base):

    __tablename__ = "institution_keys"

    id = Column(
        String,
        primary_key=True
    )

    institution_id = Column(
        String,
        nullable=False,
        index=True
    )

    public_key = Column(
        String,
        nullable=False
    )

    private_key = Column(
        String,
        nullable=False
    )

    key_type = Column(
        String,
        default="ED25519"
    )

    status = Column(
        String,
        default="ACTIVE"
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

# =========================================
# USER ACCOUNT LINK
# Maps continuity identity
# to institution execution surfaces
# =========================================
class UserAccountLink(Base):

    __tablename__ = "user_account_links"

    id = Column(
        String,
        primary_key=True
    )

    # --------------------------------
    # USER CONTINUITY
    # --------------------------------
    railone_id = Column(
        String,
        nullable=False,
        index=True
    )

    continuity_uid = Column(
        String,
        nullable=False,
        index=True
    )

    # --------------------------------
    # INSTITUTION CONTEXT
    # --------------------------------
    institution_id = Column(
        String,
        nullable=False,
        index=True
    )

    # --------------------------------
    # EXTERNAL EXECUTION SURFACE
    # --------------------------------
    external_account_ref = Column(
        String,
        nullable=False
    )

    currency = Column(
        String,
        nullable=False
    )

    linkage_state = Column(
        String,
        default="ACTIVE"
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )