# ==============================
# execution_engine.py (FINAL)
# ==============================

from ledger.db import SessionLocal
from ledger.ledger_service import apply_transaction
from balance_engine import release_funds


def process_execution(tx):

    from ledger.ledger_service import apply_transaction

def process_execution(tx):

    session = SessionLocal()

    try:
        apply_transaction(session, tx)

        session.commit()

        return True

    except Exception as e:
        session.rollback()
        print("Execution failed:", str(e))
        return False

    finally:
        session.close()