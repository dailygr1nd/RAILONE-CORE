# ==============================
# execution_engine.py (FIXED)
# ==============================

from ledger.db import SessionLocal
from ledger.ledger_service import apply_transaction


def process_execution(tx):

    session = SessionLocal()

    try:
        print(f"⚙️ Executing TX {tx['tx_id']}")

        apply_transaction(session, tx)

        tx["status"] = "SETTLED"

        session.commit()

        print(f"✅ TX {tx['tx_id']} SETTLED")

        return True

    except Exception as e:
        session.rollback()

        tx["status"] = "FAILED"

        print(f"❌ TX FAILED: {str(e)}")

        return False

    finally:
        session.close()