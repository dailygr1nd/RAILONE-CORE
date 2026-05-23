from datetime import datetime
from uuid import uuid4

from ledger.models import (
    JournalEntry,
    ExecutionThread
)


# =========================================
# INTERNAL JOURNAL POST
# =========================================
def _post(
    session,
    utt_id,
    rtt_id,
    account_id,
    amount,
    entry_type,
    currency
):

    entry = JournalEntry(
        id=str(uuid4()),
        utt_id=utt_id,
        rtt_id=rtt_id,
        account_id=account_id,
        amount=float(amount),
        entry_type=entry_type,
        currency=currency,
        created_at=datetime.utcnow()
    )

    session.add(entry)


# =========================================
# APPLY EXECUTION THREAD
# =========================================
def apply_execution(session, execution):

    utt_id = execution["utt_id"]

    rtt_id = execution.get("rtt_id")

    sender = execution["sender_account"]
    receiver = execution["receiver_account"]

    sender_ccy = execution["currency_from"]
    receiver_ccy = execution["currency_to"]

    gross = float(execution["gross_amount"])
    net = float(execution["net_amount"])

    fee = float(execution.get("fee_amount", 0))

    # --------------------------------
    # DEBIT SENDER
    # --------------------------------
    _post(
        session,
        utt_id,
        rtt_id,
        sender,
        -gross,
        "DEBIT",
        sender_ccy
    )

    # --------------------------------
    # CREDIT RECEIVER
    # --------------------------------
    _post(
        session,
        utt_id,
        rtt_id,
        receiver,
        net,
        "CREDIT",
        receiver_ccy
    )

    # --------------------------------
    # NETWORK FEE
    # --------------------------------
    if fee > 0:

        _post(
            session,
            utt_id,
            rtt_id,
            "RAILONE-TREASURY",
            fee,
            "FEE",
            sender_ccy
        )


# =========================================
# CREATE EXECUTION THREAD
# =========================================
def create_execution_thread(
    session,
    utt_id,
    sender_account,
    receiver_account,
    currency_from,
    currency_to,
    gross_amount,
    net_amount,
    fee_amount=0.0
):

    thread = ExecutionThread(
        utt_id=utt_id,
        sender_account_id=sender_account,
        receiver_account_id=receiver_account,
        currency_from=currency_from,
        currency_to=currency_to,
        gross_amount=gross_amount,
        net_amount=net_amount,
        fee_amount=fee_amount,
        execution_state="INITIATED",
        settlement_state="PENDING"
    )

    session.add(thread)

    return thread