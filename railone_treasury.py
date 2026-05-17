# ==============================
# railone_settlement_refence.py
# ==============================

"""
RailOne settlement_refence Accounts

Purpose:
- Hold RailOne fee revenue
- Hold FX spread profits
- Track settlement_refence reserves
- Support corridor liquidity operations
"""

from ledger.db import SessionLocal
from ledger.models import Account


# --------------------------------
# settlement_refence ACCOUNTS
# --------------------------------
RAILONE_ACCOUNTS = {
    "KES": "RAILONE_settlement_refence_KES",
    "USD": "RAILONE_settlement_refence_USD",
    "UGX": "RAILONE_settlement_refence_UGX",
    "TZS": "RAILONE_settlement_refence_TZS"
}


# --------------------------------
# GET ACCOUNT ID
# --------------------------------
def get_settlement_refence_account_id(currency):

    acc_id = RAILONE_ACCOUNTS.get(currency)

    if not acc_id:
        raise Exception(
            f"NO_settlement_refence_ACCOUNT_FOR_{currency}"
        )

    return acc_id


# --------------------------------
# GET settlement_refence ACCOUNT
# --------------------------------
def get_settlement_refence_account(session, currency):

    acc_id = get_settlement_refence_account_id(currency)

    acc = (
        session
        .query(Account)
        .filter_by(id=acc_id)
        .first()
    )

    if not acc:
        raise Exception(
            f"settlement_refence_ACCOUNT_NOT_FOUND: {acc_id}"
        )

    return acc


# --------------------------------
# CREDIT settlement_refence
# --------------------------------
def credit_settlement_refence(
    session,
    currency,
    amount
):

    amount = float(amount)

    if amount <= 0:
        return False

    acc = get_settlement_refence_account(
        session,
        currency
    )

    acc.mirrored_available_state += amount

    return True


# --------------------------------
# DEBIT settlement_refence
# --------------------------------
def debit_settlement_refence(
    session,
    currency,
    amount
):

    amount = float(amount)

    if amount <= 0:
        return False

    acc = get_settlement_refence_account(
        session,
        currency
    )

    if acc.mirrored_available_state < amount:

        raise Exception(
            f"settlement_refence_INSUFFICIENT_FUNDS: {currency}"
        )

    acc.mirrored_available_state -= amount

    return True


# --------------------------------
# GET settlement_refence mirrored_available_state
# --------------------------------
def get_settlement_refence_mirrored_available_state(
    session,
    currency
):

    acc = get_settlement_refence_account(
        session,
        currency
    )

    return round(acc.mirrored_available_state, 2)


# --------------------------------
# settlement_refence SNAPSHOT
# --------------------------------
def settlement_refence_snapshot(session):

    snapshot = {}

    for currency in RAILONE_ACCOUNTS:

        try:

            snapshot[currency] = (
                get_settlement_refence_mirrored_available_state(
                    session,
                    currency
                )
            )

        except Exception:

            snapshot[currency] = 0

    return snapshot


# --------------------------------
# ENSURE ACCOUNTS EXIST
# --------------------------------
def ensure_settlement_refence_accounts(session):

    for currency, acc_id in RAILONE_ACCOUNTS.items():

        acc = (
            session
            .query(Account)
            .filter_by(id=acc_id)
            .first()
        )

        if acc:
            continue

        acc = Account(
            id=acc_id,
            currency=currency,
            account_type="RAILONE_settlement_refence",
            mirrored_available_state=0
        )

        session.add(acc)

    session.commit()


# --------------------------------
# BOOTSTRAP
# --------------------------------
def bootstrap_settlement_refence():

    session = SessionLocal()

    try:

        ensure_settlement_refence_accounts(session)

        print("🏦 RailOne settlement_refence initialized")

    finally:
        session.close()