from ledger.db import SessionLocal
from ledger.models import Account


def ensure_account_exists(account_id, provider, currency, balance):
    session = SessionLocal()

    existing = session.query(Account).filter_by(id=account_id).first()

    if not existing:
        acc = Account(
            id=account_id,
            provider=provider,
            currency=currency,
            balance=balance
        )
        session.add(acc)
        session.commit()

    session.close()