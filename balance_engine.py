# ==============================
# balance_engine.py (FINAL)
# ==============================

from ledger.models import Account



def lock_funds(session, account_id, amount):

    acc = session.get(Account, account_id)

    if not acc:
        return False, "ACCOUNT_NOT_FOUND"

    # 🔥 NON-CUSTODIAL MODE
    # Assume funds exist externally unless explicitly zero

    if acc.balance <= 0:
        return False, "NO_EXTERNAL_BALANCE"

    acc.locked_balance += amount

    return True, None


def release_funds(session, account_id, amount):

    acc = session.get(Account, account_id)

    if not acc:
        return

    acc.locked_balance -= amount

    if acc.locked_balance < 0:
        acc.locked_balance = 0


def finalize_debit(session, account_id, amount):

    acc = session.get(Account, account_id)

    if not acc:
        return

    acc.balance -= amount
    acc.locked_balance -= amount

    if acc.locked_balance < 0:
        acc.locked_balance = 0


def credit_funds(session, account_id, amount):

    acc = session.get(Account, account_id)

    if not acc:
        return

    acc.balance += amount