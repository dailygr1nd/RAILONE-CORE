from sqlalchemy.orm import Session
from .models import Account


def lock_funds(session: Session, account_id: str, amount: float):
    acc = session.query(Account).filter_by(id=account_id).with_for_update().first()

    if not acc:
        return False

    available = acc.mirrored_available_state - acc.reserved

    if available < amount:
        return False

    acc.reserved += amount
    return True


def release_funds(session: Session, account_id: str, amount: float):
    acc = session.query(Account).filter_by(id=account_id).with_for_update().first()

    if not acc or acc.reserved < amount:
        return False

    acc.reserved -= amount
    return True


def settle_funds(session: Session, account_id: str, amount: float):
    acc = session.query(Account).filter_by(id=account_id).with_for_update().first()

    if not acc or acc.reserved < amount:
        return False

    acc.reserved -= amount
    acc.mirrored_available_state -= amount

    return True