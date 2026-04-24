from ledger.db import SessionLocal
from ledger.models import Account


def get_or_create_settlement_account(provider, currency):
    session = SessionLocal()

    acc_id = f"SETTLEMENT-{provider}-{currency}"

    acc = session.query(Account).filter_by(id=acc_id).first()

    if acc:
        session.close()
        return acc_id

    acc = Account(
        id=acc_id,
        owner_id="SYSTEM",
        provider=provider,
        currency=currency,
        account_type="SETTLEMENT",
        balance=0.0
    )

    session.add(acc)
    session.commit()
    session.close()

    return acc_id