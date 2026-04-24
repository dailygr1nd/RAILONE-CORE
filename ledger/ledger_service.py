from .db import SessionLocal
from .models import JournalEntry, Transaction


# --------------------------------
# SHADOW LEDGER WRITE
# --------------------------------
def log_transaction(tx: dict):
    session = SessionLocal()

    try:
        # idempotency
        existing = session.query(Transaction).filter_by(id=tx["tx_id"]).first()
        if existing:
            return True

        sender_id = tx["sender_account"]
        receiver_id = tx["receiver_account"]

        amount = tx["amount"]
        net_amount = tx["net_amount"]

        from_ccy = tx["currency_from"]
        to_ccy = tx["currency_to"]

        # --------------------------------
        # JOURNAL ENTRIES (REFERENCE ONLY)
        # --------------------------------
        entries = [
            # sender debit
            JournalEntry(
                tx_id=tx["tx_id"],
                account_id=sender_id,
                entry_type="DEBIT",
                amount=amount,
                currency=from_ccy
            ),

            # receiver credit
            JournalEntry(
                tx_id=tx["tx_id"],
                account_id=receiver_id,
                entry_type="CREDIT",
                amount=net_amount,
                currency=to_ccy
            )
        ]

        for e in entries:
            session.add(e)

        # --------------------------------
        # TRANSACTION RECORD
        # --------------------------------
        db_tx = Transaction(
            id=tx["tx_id"],
            sender_id=sender_id,
            receiver_id=receiver_id,
            amount=amount,
            currency=from_ccy,
            status=tx.get("status"),
            route=tx.get("route_result", {}).get("best_route", {}).get("rail"),
            rail_reference=tx.get("execution", {}).get("reference")
        )

        session.add(db_tx)

        session.commit()
        return True

    except Exception as e:
        session.rollback()
        print("LEDGER ERROR:", e)
        return False

    finally:
        session.close()

        # --------------------------------
# MULTI-LEG SETTLEMENT ENGINE
# --------------------------------
from .models import JournalEntry, Account


def apply_multi_leg_entry(session, tx: dict, route_type: str):
    """
    Handles:
    - Direct transfers (same rail)
    - Cross-rail settlement via settlement accounts
    """

    sender_id = tx["sender_account"]
    receiver_id = tx["receiver_account"]
    amount = tx["net_amount"]
    currency = tx["currency_from"]

    # --------------------------------
    # LOAD ACCOUNTS
    # --------------------------------
    sender = session.query(Account).filter_by(id=sender_id).first()
    receiver = session.query(Account).filter_by(id=receiver_id).first()

    if not sender or not receiver:
        raise Exception("ACCOUNT_NOT_FOUND")

    # --------------------------------
    # DETERMINE RAILS
    # --------------------------------
    sender_rail = sender.provider
    receiver_rail = receiver.provider

    # --------------------------------
    # SAME-RAIL (simple transfer)
    # --------------------------------
    if sender_rail == receiver_rail:

        session.add(JournalEntry(
            tx_id=tx["tx_id"],
            account_id=sender_id,
            entry_type="DEBIT",
            amount=amount,
            currency=currency
        ))

        session.add(JournalEntry(
            tx_id=tx["tx_id"],
            account_id=receiver_id,
            entry_type="CREDIT",
            amount=amount,
            currency=currency
        ))

        sender.balance -= amount
        receiver.balance += amount

        return

    # --------------------------------
    # CROSS-RAIL (via settlement accounts)
    # --------------------------------
    sender_settlement = f"SETTLEMENT-{sender_rail}-{currency}"
    receiver_settlement = f"SETTLEMENT-{receiver_rail}-{currency}"

    sender_settle_acc = session.query(Account).filter_by(id=sender_settlement).first()
    receiver_settle_acc = session.query(Account).filter_by(id=receiver_settlement).first()

    if not sender_settle_acc or not receiver_settle_acc:
        raise Exception("SETTLEMENT_ACCOUNT_MISSING")

    # --------------------------------
    # LEG 1: USER → SENDER SETTLEMENT
    # --------------------------------
    session.add(JournalEntry(
        tx_id=tx["tx_id"],
        account_id=sender_id,
        entry_type="DEBIT",
        amount=amount,
        currency=currency
    ))

    session.add(JournalEntry(
        tx_id=tx["tx_id"],
        account_id=sender_settlement,
        entry_type="CREDIT",
        amount=amount,
        currency=currency
    ))

    sender.balance -= amount
    sender_settle_acc.balance += amount

    # --------------------------------
    # LEG 2: RECEIVER SETTLEMENT → USER
    # --------------------------------
    session.add(JournalEntry(
        tx_id=tx["tx_id"],
        account_id=receiver_settlement,
        entry_type="DEBIT",
        amount=amount,
        currency=currency
    ))

    session.add(JournalEntry(
        tx_id=tx["tx_id"],
        account_id=receiver_id,
        entry_type="CREDIT",
        amount=amount,
        currency=currency
    ))

    receiver_settle_acc.balance -= amount
    receiver.balance += amount