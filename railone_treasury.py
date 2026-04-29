# ==============================
# railone_treasury.py
# ==============================

from ledger.db import SessionLocal
from ledger.models import Account


RAILONE_ACCOUNTS = {
    "KES": "RAILONE_TREASURY_KES",
    "USD": "RAILONE_TREASURY_USD",
    "UGX": "RAILONE_TREASURY_UGX",
    "TZS": "RAILONE_TREASURY_TZS"
}


def get_treasury_account(session, currency: str):
    acc_id = RAILONE_ACCOUNTS.get(currency)

    if not acc_id:
        raise Exception(f"NO_TREASURY_ACCOUNT_FOR_{currency}")

    acc = session.query(Account).filter_by(id=acc_id).first()

    if not acc:
        raise Exception(f"TREASURY_ACCOUNT_NOT_FOUND: {acc_id}")

    return acc


def credit_treasury(session, currency: str, amount: float):
    acc = get_treasury_account(session, currency)
    acc.balance += amount


def ensure_treasury_accounts(session):
    for currency, acc_id in RAILONE_ACCOUNTS.items():
        acc = session.query(Account).filter_by(id=acc_id).first()

        if not acc:
            acc = Account(
                id=acc_id,
                currency=currency,
                account_type="RAILONE_TREASURY",
                balance=0
            )
            session.add(acc)

    session.commit()