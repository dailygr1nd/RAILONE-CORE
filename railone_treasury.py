# ==============================
# railone_settlement_reference.py
# ==============================

"""
RailOne settlement_reference Accounts

Purpose:
- Hold RailOne fee revenue
- Hold FX spread profits
- Track settlement_reference reserves
- Support corridor liquidity operations
"""

from ledger.db import SessionLocal
from ledger.models import Account


# --------------------------------
# settlement_reference ACCOUNTS
# --------------------------------
RAILONE_ACCOUNTS = {
    "KES": "RAILONE_settlement_reference_KES",
    "USD": "RAILONE_settlement_reference_USD",
    "UGX": "RAILONE_settlement_reference_UGX",
    "TZS": "RAILONE_settlement_reference_TZS"
}


# --------------------------------
# GET ACCOUNT ID
# --------------------------------
def get_settlement_reference_account_id(currency):

    acc_id = RAILONE_ACCOUNTS.get(currency)

    if not acc_id:
        raise Exception(
            f"NO_settlement_reference_ACCOUNT_FOR_{currency}"
        )

    return acc_id


# --------------------------------
# GET settlement_reference ACCOUNT
# --------------------------------
def get_settlement_reference_account(session, currency):

    acc_id = get_settlement_reference_account_id(currency)

    acc = (
        session
        .query(Account)
        .filter_by(id=acc_id)
        .first()
    )

    if not acc:
        raise Exception(
            f"settlement_reference_ACCOUNT_NOT_FOUND: {acc_id}"
        )

    return acc


# --------------------------------
# CREDIT settlement_reference
# --------------------------------
def credit_settlement_reference(
    session,
    currency,
    amount
):

    amount = float(amount)

    if amount <= 0:
        return False

    acc = get_settlement_reference_account(
        session,
        currency
    )

    acc.mirrored_available_state += amount

    return True


# --------------------------------
# DEBIT settlement_reference
# --------------------------------
def debit_settlement_reference(
    session,
    currency,
    amount
):

    amount = float(amount)

    if amount <= 0:
        return False

    acc = get_settlement_reference_account(
        session,
        currency
    )

    if acc.mirrored_available_state < amount:

        raise Exception(
            f"settlement_reference_INSUFFICIENT_FUNDS: {currency}"
        )

    acc.mirrored_available_state -= amount

    return True


# --------------------------------
# GET settlement_reference mirrored_available_state
# --------------------------------
def get_settlement_reference_mirrored_available_state(
    session,
    currency
):

    acc = get_settlement_reference_account(
        session,
        currency
    )

    return round(acc.mirrored_available_state, 2)


# --------------------------------
# settlement_reference SNAPSHOT
# --------------------------------
def settlement_reference_snapshot(session):

    snapshot = {}

    for currency in RAILONE_ACCOUNTS:

        try:

            snapshot[currency] = (
                get_settlement_reference_mirrored_available_state(
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
def ensure_settlement_reference_accounts(session):

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
            account_type="RAILONE_settlement_reference",
            mirrored_available_state=0
        )

        session.add(acc)

    session.commit()


# --------------------------------
# BOOTSTRAP
# --------------------------------
def bootstrap_settlement_reference():

    session = SessionLocal()

    try:

        ensure_settlement_reference_accounts(session)

        print("🏦 RailOne settlement_reference initialized")

    finally:
        session.close()