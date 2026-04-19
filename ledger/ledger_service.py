from sqlalchemy.orm import Session
from .models import LedgerEntry, Account


def apply_double_entry(session: Session, tx_id, sender_id, receiver_id, amount, currency):

    sender = session.query(Account).filter_by(id=sender_id).first()
    receiver = session.query(Account).filter_by(id=receiver_id).first()

    if sender.balance < amount:
        raise Exception("Insufficient funds")

    # debit sender
    sender.balance -= amount

    entry1 = LedgerEntry(
        tx_id=tx_id,
        account_id=sender_id,
        debit=amount,
        credit=0,
        currency=currency
    )

    # credit receiver
    receiver.balance += amount

    entry2 = LedgerEntry(
        tx_id=tx_id,
        account_id=receiver_id,
        debit=0,
        credit=amount,
        currency=currency
    )

    session.add(entry1)
    session.add(entry2)

    session.commit()