from ledger.db import SessionLocal
from ledger.models import Account


# --------------------------------
# GET ACCOUNT
# --------------------------------
def get_account(session, account_id):

    acc = session.query(Account).filter_by(id=account_id).first()

    if not acc:
        acc = Account(id=account_id, balance=0.0, reserved=0.0)
        session.add(acc)

    return acc


# --------------------------------
# AVAILABLE BALANCE
# --------------------------------
def get_available_balance(session, account_id):

    acc = get_account(session, account_id)
    return acc.balance - acc.reserved


# --------------------------------
# RESERVE FUNDS (LOCK)
# --------------------------------
def reserve_funds(session, account_id, amount):

    acc = get_account(session, account_id)

    if (acc.balance - acc.reserved) < amount:
        return False, "INSUFFICIENT_FUNDS"

    acc.reserved += amount
    return True, None


# --------------------------------
# RELEASE FUNDS (FAIL CASE)
# --------------------------------
def release_funds(session, account_id, amount):

    acc = get_account(session, account_id)
    acc.reserved -= amount

    if acc.reserved < 0:
        acc.reserved = 0


# --------------------------------
# FINALIZE DEBIT (SETTLEMENT)
# --------------------------------
def finalize_debit(session, account_id, amount):

    acc = get_account(session, account_id)

    acc.reserved -= amount
    acc.balance -= amount


# --------------------------------
# CREDIT FUNDS
# --------------------------------
def credit_funds(session, account_id, amount):

    acc = get_account(session, account_id)
    acc.balance += amount