# ==============================
# railone_treasury.py
# ==============================

"""
RailOne Treasury Accounts

Purpose:
- Hold RailOne fee revenue
- Hold FX spread profits
- Track treasury reserves
- Support corridor liquidity operations
"""

from ledger.db import SessionLocal
from ledger.models import Account


# --------------------------------
# TREASURY ACCOUNTS
# --------------------------------
RAILONE_ACCOUNTS = {
    "KES": "RAILONE_TREASURY_KES",
    "USD": "RAILONE_TREASURY_USD",
    "UGX": "RAILONE_TREASURY_UGX",
    "TZS": "RAILONE_TREASURY_TZS"
}


# --------------------------------
# GET ACCOUNT ID
# --------------------------------
def get_treasury_account_id(currency):

    acc_id = RAILONE_ACCOUNTS.get(currency)

    if not acc_id:
        raise Exception(
            f"NO_TREASURY_ACCOUNT_FOR_{currency}"
        )

    return acc_id


# --------------------------------
# GET TREASURY ACCOUNT
# --------------------------------
def get_treasury_account(session, currency):

    acc_id = get_treasury_account_id(currency)

    acc = (
        session
        .query(Account)
        .filter_by(id=acc_id)
        .first()
    )

    if not acc:
        raise Exception(
            f"TREASURY_ACCOUNT_NOT_FOUND: {acc_id}"
        )

    return acc


# --------------------------------
# CREDIT TREASURY
# --------------------------------
def credit_treasury(
    session,
    currency,
    amount
):

    amount = float(amount)

    if amount <= 0:
        return False

    acc = get_treasury_account(
        session,
        currency
    )

    acc.balance += amount

    return True


# --------------------------------
# DEBIT TREASURY
# --------------------------------
def debit_treasury(
    session,
    currency,
    amount
):

    amount = float(amount)

    if amount <= 0:
        return False

    acc = get_treasury_account(
        session,
        currency
    )

    if acc.balance < amount:

        raise Exception(
            f"TREASURY_INSUFFICIENT_FUNDS: {currency}"
        )

    acc.balance -= amount

    return True


# --------------------------------
# GET TREASURY BALANCE
# --------------------------------
def get_treasury_balance(
    session,
    currency
):

    acc = get_treasury_account(
        session,
        currency
    )

    return round(acc.balance, 2)


# --------------------------------
# TREASURY SNAPSHOT
# --------------------------------
def treasury_snapshot(session):

    snapshot = {}

    for currency in RAILONE_ACCOUNTS:

        try:

            snapshot[currency] = (
                get_treasury_balance(
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
def ensure_treasury_accounts(session):

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
            account_type="RAILONE_TREASURY",
            balance=0
        )

        session.add(acc)

    session.commit()


# --------------------------------
# BOOTSTRAP
# --------------------------------
def bootstrap_treasury():

    session = SessionLocal()

    try:

        ensure_treasury_accounts(session)

        print("🏦 RailOne treasury initialized")

    finally:
        session.close()