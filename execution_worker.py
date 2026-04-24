# ==============================
# execution_worker.py (CLEAN PRO)
# ==============================

import time
import redis

from execution_queue import dequeue_tx, send_to_dead_letter
from execution_engine import process_execution

from balance_engine import release_funds
from treasury_engine import needs_rebalance, rebalance_pool

from ledger.db import SessionLocal


# --------------------------------
# REDIS (REPLAY PROTECTION)
# --------------------------------
r = redis.Redis(host="localhost", port=6379, decode_responses=True)


def already_processed(tx_id):
    return r.get(f"processed:{tx_id}") is not None


def mark_processed(tx_id):
    r.setex(f"processed:{tx_id}", 3600, "1")  # 1 hour TTL


# --------------------------------
# TREASURY HOOK
# --------------------------------
def run_rebalancing():
    session = SessionLocal()

    try:
        for ccy in ["KES", "TZS", "UGX"]:
            if needs_rebalance(session, ccy):
                rebalance_pool(session, ccy)

        session.commit()

    except Exception as e:
        print(f"⚠️ Treasury rebalance error: {str(e)}")
        session.rollback()

    finally:
        session.close()


# --------------------------------
# SAFE EXECUTION WRAPPER
# --------------------------------
def safe_execute(tx):

    tx_id = tx["tx_id"]

    # ✅ Replay protection FIRST
    if already_processed(tx_id):
        print(f"⚠️ Replay blocked: {tx_id}")
        return True

    try:
        print(f"⚙️ Executing TX {tx_id}")

        success = process_execution(tx)

        if success:
            mark_processed(tx_id)

            # ✅ Post-settlement treasury check
            run_rebalancing()

            print(f"✅ TX {tx_id} SETTLED")
            return True

        else:
            print(f"❌ TX {tx_id} FAILED (execution)")
            return False

    except Exception as e:
        print(f"💥 Execution error: {str(e)}")

        # 🔥 CRITICAL: release locked funds
        try:
            session = SessionLocal()

            release_funds(
                session,
                tx["sender_account"],
                tx["gross_amount"]
            )

            session.commit()
            session.close()

            print("🔓 Funds released")

        except Exception as e2:
            print(f"❌ Failed to release funds: {str(e2)}")

        return False


# --------------------------------
# WORKER LOOP
# --------------------------------
def start_worker():

    print("🚀 Execution Worker Started")

    while True:

        try:
            tx = dequeue_tx()

            if not tx:
                time.sleep(1)
                continue

            print(f"\n📥 Picked TX {tx['tx_id']}")

            success = safe_execute(tx)

            if not success:
                send_to_dead_letter(tx, "EXECUTION_FAILED")

        except Exception as loop_error:
            print(f"💥 Worker loop error: {str(loop_error)}")
            time.sleep(2)  # prevent crash loop


# --------------------------------
# ENTRY
# --------------------------------
if __name__ == "__main__":
    start_worker()