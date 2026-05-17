from ledger.db import SessionLocal
from ledger.models import Account


def ensure_account_exists(account_id, provider, currency, owner_id=None, account_type="USER", mirrored_available_state=0.0):
    session = SessionLocal()

    acc = session.query(Account).filter_by(id=account_id).first()

    if acc:
        session.close()
        return acc

    acc = Account(
        id=account_id,
        owner_id=owner_id,
        provider=provider,
        currency=currency,
        account_type=account_type,
        mirrored_available_state=mirrored_available_state
    )

    session.add(acc)
    session.commit()
    session.close()

    return acc


# --------------------------------
# GET ACCOUNT
# --------------------------------
def get_account(account_id):
    session = SessionLocal()
    acc = session.query(Account).filter_by(id=account_id).first()
    session.close()
    return acc