# ==============================
# ledger/ledger_service.py (PRO)
# ==============================

from datetime import datetime
from uuid import uuid4

from ledger.models import JournalEntry
from balance_engine import finalize_debit, credit_funds

from rails_config import RAILS
from liquidity_pools import POOLS


# --------------------------------
# INTERNAL POST
# --------------------------------
def _post(session, tx_id, account_id, amount, entry_type, currency):

    entry = JournalEntry(
        id=str(uuid4()),
        tx_id=tx_id,
        account_id=account_id,
        amount=float(amount),
        entry_type=entry_type,
        currency=currency,
        created_at=datetime.utcnow()
    )

    session.add(entry)


# --------------------------------
# APPLY TRANSACTION (MULTI-LEG)
# --------------------------------
def apply_transaction(session, tx):

    tx_id = tx["tx_id"]

    sender = tx["sender_account"]
    receiver = tx["receiver_account"]

    sender_inst = sender.split("-")[0]
    receiver_inst = receiver.split("-")[0]

    sender_ccy = tx["currency_from"]
    receiver_ccy = tx["currency_to"]

    gross = float(tx["gross_amount"])
    net = float(tx["net_amount"])
    fee = float(tx.get("fees", 0))

    revenue_account = "RAILONE_REVENUE"

    sender_settlement = RAILS[sender_inst]["settlement_account"]
    receiver_settlement = RAILS[receiver_inst]["settlement_account"]

    pool_from = POOLS[sender_ccy]
    pool_to = POOLS[receiver_ccy]

    # =====================================
    # LEG 1: USER → SENDER SETTLEMENT
    # =====================================
    _post(session, tx_id, sender, gross, "DEBIT", sender_ccy)
    _post(session, tx_id, sender_settlement, gross, "CREDIT", sender_ccy)

    # =====================================
    # LEG 2: SETTLEMENT → SOURCE POOL
    # =====================================
    _post(session, tx_id, sender_settlement, gross, "DEBIT", sender_ccy)
    _post(session, tx_id, pool_from, gross, "CREDIT", sender_ccy)

    # =====================================
    # LEG 3: FX SWAP (POOL → POOL)
    # =====================================
    _post(session, tx_id, pool_from, gross, "DEBIT", sender_ccy)
    _post(session, tx_id, pool_to, net, "CREDIT", receiver_ccy)

    # =====================================
    # LEG 4: DESTINATION SETTLEMENT
    # =====================================
    _post(session, tx_id, pool_to, net, "DEBIT", receiver_ccy)
    _post(session, tx_id, receiver_settlement, net, "CREDIT", receiver_ccy)

    # =====================================
    # LEG 5: RECEIVER CREDIT
    # =====================================
    _post(session, tx_id, receiver_settlement, net, "DEBIT", receiver_ccy)
    _post(session, tx_id, receiver, net, "CREDIT", receiver_ccy)

    # =====================================
    # FEES (SOURCE SIDE)
    # =====================================
    if fee > 0:
        _post(session, tx_id, sender, fee, "DEBIT", sender_ccy)
        _post(session, tx_id, revenue_account, fee, "CREDIT", sender_ccy)

    # =====================================
    # BALANCE FINALIZATION
    # =====================================
    finalize_debit(session, sender, gross + fee)
    credit_funds(session, receiver, net)

    if fee > 0:
        credit_funds(session, revenue_account, fee)


# --------------------------------
# GENESIS FUNDING
# --------------------------------
def apply_genesis(session, account_id, amount):

    currency = account_id.split("-")[-1]

    exists = session.query(JournalEntry).filter_by(
        tx_id="GENESIS",
        account_id=account_id
    ).first()

    if exists:
        return

    _post(session, "GENESIS", account_id, amount, "CREDIT", currency)

    credit_funds(session, account_id, float(amount))