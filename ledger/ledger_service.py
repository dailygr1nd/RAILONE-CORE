# ==============================
# ledger_service.py (FINAL CLEAN)
# ==============================

from datetime import datetime
from decimal import Decimal

from ledger.models import JournalEntry, Account


# --------------------------------
# CORE POSTING FUNCTION
# --------------------------------
def _post(session, tx_id, account_id, amount, entry_type, currency):
    entry = JournalEntry(
        tx_id=tx_id,
        account_id=account_id,
        amount=float(amount),
        entry_type=entry_type,
        currency=currency,
        created_at=datetime.utcnow()
    )
    session.add(entry)


# --------------------------------
# BALANCE UPDATE (CACHE ONLY)
# --------------------------------
def _apply_balance_delta(session, account_id, delta):
    acc = session.query(Account).filter_by(id=account_id).first()

    if not acc:
        acc = Account(id=account_id, balance=0.0)
        session.add(acc)

    acc.balance += float(delta)


# --------------------------------
# APPLY TRANSACTION (DOUBLE ENTRY)
# --------------------------------
def apply_transaction(session, tx: dict):

    tx_id = tx["tx_id"]
    route = tx["route_result"]

    if not route or not route.get("steps"):
        raise ValueError("INVALID_ROUTE")

    fx_rate = route.get("fx_rate", 1.0)

    amount = float(tx["gross_amount"])

    for step in route["steps"]:

        from_acc = step["from"]
        to_acc = step["to"]
        action = step["action"]

        from_ccy = from_acc.split("-")[-1]
        to_ccy = to_acc.split("-")[-1]

        # --------------------------------
        # TRANSFER LEG
        # --------------------------------
        if action == "TRANSFER":

            _post(session, tx_id, from_acc, amount, "DEBIT", from_ccy)
            _post(session, tx_id, to_acc, amount, "CREDIT", to_ccy)

            _apply_balance_delta(session, from_acc, -amount)
            _apply_balance_delta(session, to_acc, amount)

        # --------------------------------
        # FX LEG
        # --------------------------------
        elif action == "FX":

            converted = round(amount * fx_rate, 2)

            fx_pool_from = f"FX_POOL-{from_ccy}"
            fx_pool_to = f"FX_POOL-{to_ccy}"

            # debit source pool
            _post(session, tx_id, fx_pool_from, amount, "DEBIT", from_ccy)

            # credit destination pool
            _post(session, tx_id, fx_pool_to, converted, "CREDIT", to_ccy)

            _apply_balance_delta(session, fx_pool_from, -amount)
            _apply_balance_delta(session, fx_pool_to, converted)

            # update working amount for next leg
            amount = converted


            revenue_account = "RAILONE_REVENUE"

    # --------------------------------
    # OPTIONAL: PLATFORM FEE
    # --------------------------------
    # --------------------------------
# PLATFORM FEE
# --------------------------------
    fee = float(tx.get("fees", 0))

    if fee > 0:
     sender = tx["sender_account"]
    revenue_account = "RAILONE_REVENUE"

    currency = sender.split("-")[-1]

    _post(session, tx_id, sender, fee, "DEBIT", currency)
    _post(session, tx_id, revenue_account, fee, "CREDIT", currency)

    _apply_balance_delta(session, sender, -fee)
    _apply_balance_delta(session, revenue_account, fee)


# --------------------------------
# GENESIS (ONLY FUNDING ENTRY)
# --------------------------------
def apply_genesis(session, account_id: str, amount: float):

    currency = account_id.split("-")[-1]

    _post(session, "GENESIS", account_id, amount, "CREDIT", currency)

    acc = session.query(Account).filter_by(id=account_id).first()

    if not acc:
        acc = Account(id=account_id, balance=0.0)
        session.add(acc)

    acc.balance += float(amount)