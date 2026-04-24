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