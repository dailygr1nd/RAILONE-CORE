# ==============================
# ledger_service.py (FINAL SAFE)
# ==============================

from datetime import datetime
from uuid import uuid4

from ledger.models import JournalEntry, Account
from balance_engine import finalize_debit, credit_funds


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
# APPLY TRANSACTION
# --------------------------------
def apply_transaction(session, tx):

    from balance_engine import finalize_debit, credit_funds

def apply_transaction(session, tx):

    tx_id = tx["tx_id"]

    sender = tx["sender_account"]
    receiver = tx["receiver_account"]

    sender_ccy = tx["currency_from"]
    receiver_ccy = tx["currency_to"]

    gross = tx["gross_amount"]
    net = tx["net_amount"]
    fee = tx.get("fee", 0)

    # --------------------------------
    # LEDGER POSTS (SIMPLIFIED CORE)
    # --------------------------------
    _post(session, tx_id, sender, gross, "DEBIT", sender_ccy)
    _post(session, tx_id, receiver, net, "CREDIT", receiver_ccy)

    if fee > 0:
        _post(session, tx_id, sender, fee, "DEBIT", sender_ccy)
        _post(session, tx_id, "RAILONE_REVENUE", fee, "CREDIT", sender_ccy)

    # --------------------------------
    # BALANCE FINALIZATION
    # --------------------------------
    finalize_debit(session, sender, gross + fee)
    credit_funds(session, receiver, net)

    # -----------------------------
    # JOURNAL ENTRIES
    # -----------------------------

    _post(session, tx_id, sender, gross, "DEBIT", sender_ccy)
    _post(session, tx_id, receiver, net, "CREDIT", receiver_ccy)

    if fee > 0:
        revenue_account = f"RAILONE_REVENUE-{sender_ccy}"

        _post(session, tx_id, sender, fee, "DEBIT", sender_ccy)
        _post(session, tx_id, revenue_account, fee, "CREDIT", sender_ccy)

    # -----------------------------
    # BALANCE UPDATES
    # -----------------------------

    finalize_debit(session, sender, gross + fee)
    credit_funds(session, receiver, net)

    if fee > 0:
        credit_funds(session, revenue_account, fee)

    _validate_transaction(session, tx_id)


# --------------------------------
# INTEGRITY CHECK
# --------------------------------
def _validate_transaction(session, tx_id):

    entries = session.query(JournalEntry).filter_by(tx_id=tx_id).all()

    currency_map = {}

    for e in entries:

        if e.currency not in currency_map:
            currency_map[e.currency] = 0

        if e.entry_type == "DEBIT":
            currency_map[e.currency] -= e.amount
        else:
            currency_map[e.currency] += e.amount

    for ccy, total in currency_map.items():
        if round(total, 2) != 0:
            raise Exception(f"LEDGER_IMBALANCE: {ccy} → {total}")
        
        # --------------------------------
# GENESIS FUNDING
# --------------------------------
def apply_genesis(session, account_id, amount):

    from ledger.models import Account

    currency = account_id.split("-")[-1]

    # create account if not exists
    acc = session.query(Account).filter_by(id=account_id).first()

    if not acc:
        acc = Account(
            id=account_id,
            currency=currency,
            account_type="USER",
            balance=0.0,
            locked_balance=0.0,
            allow_overdraft="false"
        )
        session.add(acc)

    # prevent duplicate genesis
    exists = session.query(JournalEntry).filter_by(
        tx_id="GENESIS",
        account_id=account_id
    ).first()

    if exists:
        return

    # journal entry
    _post(session, "GENESIS", account_id, amount, "CREDIT", currency)

    # update balance
    acc.balance += float(amount)