# ==============================
# mirrored_available_state_engine.py (FINAL)
# ==============================

from ledger.models import Account



def lock_funds(session, account_id, amount):

    acc = session.get(Account, account_id)

    if not acc:
        return False, "ACCOUNT_NOT_FOUND"

    # 🔥 NON-CUSTODIAL MODE
    # Assume funds exist externally unless explicitly zero

    if acc.mirrored_available_state <= 0:
        return False, "NO_EXTERNAL_mirrored_available_state"

    acc.execution_reservation += amount

    return True, None


def release_funds(session, account_id, amount):

    acc = session.get(Account, account_id)

    if not acc:
        return

    acc.execution_reservation -= amount

    if acc.execution_reservation < 0:
        acc.execution_reservation = 0


def finalize_debit(session, account_id, amount):

    acc = session.get(Account, account_id)

    if not acc:
        return

    acc.mirrored_available_state -= amount
    acc.execution_reservation -= amount

    if acc.execution_reservation < 0:
        acc.execution_reservation = 0


def credit_funds(session, account_id, amount):

    acc = session.get(Account, account_id)

    if not acc:
        return

    acc.mirrored_available_state += amount