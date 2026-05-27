# ==========================================
# ledger/models.py
# RailOne Canonical Ledger Models
# ==========================================

import uuid

from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Float,
    Integer,
    Boolean,
    DateTime,
    JSON,
    Text
)

from ledger.db import Base


# ==========================================
# EXECUTION ACCOUNT
# Non-custodial mirrored execution surface
# ==========================================
class Account(Base):

    __tablename__ = "accounts"

    id = Column(
        String,
        primary_key=True
    )

    # ======================================
    # CONTINUITY IDENTITY
    # ======================================
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

    # ======================================
    # INSTITUTION CONTEXT
    # ======================================
    institution_id = Column(
        String,
        nullable=False,
        index=True
    )

    adapter_type = Column(
        String,
        nullable=True,
        index=True
    )

    # ======================================
    # EXECUTION CAPACITY
    # ======================================
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

    execution_capacity = Column(
        Float,
        default=0.0
    )

    # ======================================
    # PROVIDER CONTEXT
    # ======================================
    external_account_reference = Column(
        String,
        nullable=True
    )

    provider_metadata = Column(
        JSON,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


# ==========================================
# EXECUTION THREAD
# Canonical continuity object
# ==========================================
class ExecutionThread(Base):

    __tablename__ = "execution_threads"

    utt_id = Column(
        String,
        primary_key=True
    )

    # ======================================
    # CONTINUITY CONTEXT
    # ======================================
    continuity_uid = Column(
        String,
        nullable=False,
        index=True
    )

    replay_generation = Column(
        Integer,
        default=0
    )

    lineage_parent = Column(
        String,
        nullable=True,
        index=True
    )

    # ======================================
    # EXECUTION STATE
    # ======================================
    execution_state = Column(
        String,
        default="INITIATED"
    )

    canonical_execution_state = Column(
        String,
        nullable=True
    )

    settlement_state = Column(
        String,
        default="PENDING"
    )

    divergence_detected = Column(
        Boolean,
        default=False
    )

    divergence_type = Column(
        String,
        nullable=True
    )

    replay_integrity_verified = Column(
        Boolean,
        default=False
    )

    # ======================================
    # ROUTE CONTEXT
    # ======================================
    current_rtt_id = Column(
        String,
        nullable=True
    )

    route_generation = Column(
        Integer,
        default=1
    )

    # ======================================
    # PROVIDER CONTEXT
    # ======================================
    provider = Column(
        String,
        nullable=True,
        index=True
    )

    provider_reference = Column(
        String,
        nullable=True,
        index=True
    )

    adapter_type = Column(
        String,
        nullable=True
    )

    # ======================================
    # PARTICIPANTS
    # ======================================
    sender_account_id = Column(
        String,
        nullable=False
    )

    receiver_account_id = Column(
        String,
        nullable=False
    )

    # ======================================
    # VALUE CONTEXT
    # ======================================
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

    # ======================================
    # EXECUTION METADATA
    # ======================================
    execution_metadata = Column(
        JSON,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


# ==========================================
# ROUTE EXECUTION
# Realized execution path
# ==========================================
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

    continuity_uid = Column(
        String,
        nullable=False,
        index=True
    )

    # ======================================
    # ROUTE CONTEXT
    # ======================================
    route_state = Column(
        String,
        default="ROUTED"
    )

    route_generation = Column(
        Integer,
        default=1
    )

    institution_path = Column(
        JSON,
        nullable=True
    )

    adapter_path = Column(
        JSON,
        nullable=True
    )

    # ======================================
    # PROVIDER REALIZATION
    # ======================================
    provider = Column(
        String,
        nullable=True
    )

    provider_reference = Column(
        String,
        nullable=True
    )

    canonical_execution_state = Column(
        String,
        nullable=True
    )

    # ======================================
    # CONTINUITY ASSURANCE
    # ======================================
    replay_safe_hash = Column(
        String,
        nullable=True
    )

    replay_integrity_verified = Column(
        Boolean,
        default=False
    )

    divergence_detected = Column(
        Boolean,
        default=False
    )

    divergence_type = Column(
        String,
        nullable=True
    )

    # ======================================
    # EXECUTION ATTESTATIONS
    # ======================================
    execution_attestation = Column(
        Text,
        nullable=True
    )

    route_attestation = Column(
        Text,
        nullable=True
    )

    settlement_provenance = Column(
        Text,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


# ==========================================
# JOURNAL ENTRIES
# Accounting truth only
# ==========================================
class JournalEntry(Base):

    __tablename__ = "journal_entries"

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    # ======================================
    # CONTINUITY CONTEXT
    # ======================================
    continuity_uid = Column(
        String,
        nullable=False,
        index=True
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

    # ======================================
    # ACCOUNTING CONTEXT
    # ======================================
    account_id = Column(
        String,
        nullable=False
    )

    institution_id = Column(
        String,
        nullable=True
    )

    provider = Column(
        String,
        nullable=True
    )

    # ======================================
    # VALUE CONTEXT
    # ======================================
    amount = Column(
        Float,
        nullable=False
    )

    currency = Column(
        String,
        nullable=False
    )

    entry_type = Column(
        String,
        nullable=False
    )

    canonical_execution_state = Column(
        String,
        nullable=True
    )

    # ======================================
    # ASSURANCE CONTEXT
    # ======================================
    replay_safe_hash = Column(
        String,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


# ==========================================
# INSTITUTION
# Capability + trust domain
# ==========================================
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

    country = Column(
        String,
        nullable=False
    )

    operational_status = Column(
        String,
        default="ACTIVE"
    )

    # ======================================
    # EXECUTION CAPABILITIES
    # ======================================
    supported_adapters = Column(
        JSON,
        nullable=True
    )

    supported_currencies = Column(
        JSON,
        nullable=True
    )

    replay_policy = Column(
        JSON,
        nullable=True
    )

    execution_policy = Column(
        JSON,
        nullable=True
    )

    attestation_capable = Column(
        Boolean,
        default=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


# ==========================================
# USER ACCOUNT LINK
# External execution linkage
# ==========================================
class UserAccountLink(Base):

    __tablename__ = "user_account_links"

    id = Column(
        String,
        primary_key=True
    )

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

    institution_id = Column(
        String,
        nullable=False,
        index=True
    )

    adapter_type = Column(
        String,
        nullable=True
    )

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

    attestation_reference = Column(
        String,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )