# ==========================================
# ledger/ledger_service.py
# RailOne Ledger Coordination Service
# ==========================================

import uuid

from datetime import datetime

from ledger.db import SessionLocal

from ledger.models import (
    Account,
    JournalEntry,
    ExecutionThread
)

from execution.events.event_store import (
    emit_event
)


class LedgerService:

    # ======================================
    # RESERVE EXECUTION CAPACITY
    # ======================================
    @staticmethod
    def reserve_execution_capacity(

        account_id,

        amount,

        utt_id,

        rtt_id=None
    ):

        session = SessionLocal()

        try:

            account = (

                session.query(Account)

                .filter(
                    Account.id == account_id
                )

                .first()
            )

            if not account:

                raise Exception(
                    "ACCOUNT_NOT_FOUND"
                )

            available_capacity = (

                account
                .mirrored_available_state

                -

                account
                .execution_reservation
            )

            if available_capacity < amount:

                raise Exception(
                    "INSUFFICIENT_"
                    "EXECUTION_CAPACITY"
                )

            account.execution_reservation += (
                amount
            )

            session.commit()

            emit_event(

                utt_id=utt_id,

                rtt_id=rtt_id,

                continuity_uid=(
                    account.continuity_uid
                ),

                event_type=(
                    "EXECUTION_CAPACITY_RESERVED"
                ),

                payload={

                    "account_id":
                        account_id,

                    "amount":
                        amount
                }
            )

            return {

                "success": True,

                "reserved_amount":
                    amount
            }

        finally:

            session.close()

    # ======================================
    # RELEASE EXECUTION CAPACITY
    # ======================================
    @staticmethod
    def release_execution_capacity(

        account_id,

        amount,

        utt_id,

        rtt_id=None
    ):

        session = SessionLocal()

        try:

            account = (

                session.query(Account)

                .filter(
                    Account.id == account_id
                )

                .first()
            )

            if not account:

                raise Exception(
                    "ACCOUNT_NOT_FOUND"
                )

            account.execution_reservation -= (
                amount
            )

            if (
                account.execution_reservation
                < 0
            ):

                account.execution_reservation = 0

            session.commit()

            emit_event(

                utt_id=utt_id,

                rtt_id=rtt_id,

                continuity_uid=(
                    account.continuity_uid
                ),

                event_type=(
                    "EXECUTION_CAPACITY_RELEASED"
                ),

                payload={

                    "account_id":
                        account_id,

                    "amount":
                        amount
                }
            )

            return {

                "success": True
            }

        finally:

            session.close()

    # ======================================
    # FINALIZE EXECUTION
    # ======================================
    @staticmethod
    def finalize_execution(

        sender_account_id,

        receiver_account_id,

        amount,

        currency,

        utt_id,

        rtt_id=None,

        provider=None
    ):

        session = SessionLocal()

        try:

            sender = (

                session.query(Account)

                .filter(
                    Account.id
                    == sender_account_id
                )

                .first()
            )

            receiver = (

                session.query(Account)

                .filter(
                    Account.id
                    == receiver_account_id
                )

                .first()
            )

            if not sender or not receiver:

                raise Exception(
                    "ACCOUNT_NOT_FOUND"
                )

            # ===============================
            # UPDATE EXECUTION SURFACES
            # ===============================
            sender.execution_reservation -= (
                amount
            )

            sender.mirrored_available_state -= (
                amount
            )

            receiver.mirrored_available_state += (
                amount
            )

            # ===============================
            # JOURNAL ENTRIES
            # ===============================
            debit_entry = JournalEntry(

                id=str(uuid.uuid4()),

                continuity_uid=(
                    sender.continuity_uid
                ),

                utt_id=utt_id,

                rtt_id=rtt_id,

                account_id=(
                    sender_account_id
                ),

                institution_id=(
                    sender.institution_id
                ),

                provider=provider,

                amount=-amount,

                currency=currency,

                entry_type="DEBIT",

                canonical_execution_state=(
                    "execution_settled"
                )
            )

            credit_entry = JournalEntry(

                id=str(uuid.uuid4()),

                continuity_uid=(
                    receiver.continuity_uid
                ),

                utt_id=utt_id,

                rtt_id=rtt_id,

                account_id=(
                    receiver_account_id
                ),

                institution_id=(
                    receiver.institution_id
                ),

                provider=provider,

                amount=amount,

                currency=currency,

                entry_type="CREDIT",

                canonical_execution_state=(
                    "execution_settled"
                )
            )

            session.add(debit_entry)

            session.add(credit_entry)

            session.commit()

            emit_event(

                utt_id=utt_id,

                rtt_id=rtt_id,

                continuity_uid=(
                    sender.continuity_uid
                ),

                event_type=(
                    "EXECUTION_FINALIZED"
                ),

                provider=provider,

                canonical_state=(
                    "execution_settled"
                )
            )

            return {

                "success": True
            }

        finally:

            session.close()