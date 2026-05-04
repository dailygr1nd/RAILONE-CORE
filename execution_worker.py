# ==============================
# execution_worker.py (EVENT-DRIVEN)
# ==============================

import time
import redis

from execution_queue import dequeue_tx, send_to_dead_letter, update_tx
from execution_engine import process_execution

from balance_engine import release_funds
from treasury_engine import needs_rebalance, rebalance_pool

from revenue_engine import extract_revenue
from ledger.db import SessionLocal

from tx_verifier import verify_transaction
from webhook_dispatcher import dispatch_event


r = redis.Redis(host="localhost", port=6379, decode_responses=True)


# --------------------------------
# REPLAY PROTECTION
# --------------------------------
def already_processed(tx_id):
    return r.get(f"processed:{tx_id}") is not None


def mark_processed(tx_id):
    r.setex(f"processed:{tx_id}", 3600, "1")


# --------------------------------
# TREASURY
# --------------------------------
def run_rebalancing():
    session = SessionLocal()

    try:
        for ccy in ["KES", "TZS", "UGX"]:
            if needs_rebalance(session, ccy):
                print(f"💰 Rebalancing {ccy}")
                rebalance_pool(session, ccy)

        session.commit()

    except Exception as e:
        print(f"⚠️ Treasury rebalance error: {str(e)}")
        session.rollback()

    finally:
        session.close()


# --------------------------------
# VERIFICATION GATE
# --------------------------------
def pre_verify_or_reject(tx):

    result = verify_transaction(tx)

    if not result.get("valid"):
        print(f"🚫 VERIFICATION FAILED: {tx['tx_id']}")

        for c in result.get("checks", []):
            print(f"   - {c}")

        return False, result

    return True, result


# --------------------------------
# CORE EXECUTION
# --------------------------------
def safe_execute(tx):

    tx_id = tx["tx_id"]

    if already_processed(tx_id):
        print(f"⚠️ Replay blocked: {tx_id}")
        return True

    # --------------------------------
    # VERIFY
    # --------------------------------
    verified, result = pre_verify_or_reject(tx)

    if not verified:
        dispatch_event(tx, "transaction.failed")
        return False

    session = SessionLocal()

    try:
        print(f"⚙️ Executing TX {tx_id}")

        # --------------------------------
        # 🔥 EMIT EXECUTING
        # --------------------------------
        dispatch_event(tx, "transaction.executing")

        # --------------------------------
        # EXECUTE
        # --------------------------------
        success = process_execution(tx)

        if not success:
            dispatch_event(tx, "transaction.failed")
            return False

        # --------------------------------
        # REVENUE
        # --------------------------------
        try:
            extract_revenue(session, tx)
        except Exception as rev_err:
            print(f"⚠️ Revenue extraction failed: {str(rev_err)}")

        # --------------------------------
        # MARK PROCESSED
        # --------------------------------
        mark_processed(tx_id)

        # --------------------------------
        # UPDATE STATE
        # --------------------------------
        update_tx(tx_id, {"status": "SETTLED"})
        dispatch_event(tx, "transaction.completed")

        # --------------------------------
        # TREASURY
        # --------------------------------
        run_rebalancing()

        session.commit()

        print(f"✅ TX {tx_id} SETTLED")

        return True

    except Exception as e:
        print(f"💥 Execution error: {str(e)}")

        session.rollback()

        try:
            release_funds(
                session,
                tx["sender_account"],
                tx.get("gross_amount", tx.get("amount", 0))
            )
            session.commit()
        except Exception as e2:
            print(f"❌ Failed to release funds: {str(e2)}")

        dispatch_event(tx, "transaction.failed")

        return False

    finally:
        session.close()


# --------------------------------
# WORKER LOOP
# --------------------------------
def start_worker():

    print("🚀 Execution Worker Started (EVENT DRIVEN)")

    while True:
        try:
            tx = dequeue_tx()

            if not tx:
                time.sleep(1)
                continue

            tx_id = tx["tx_id"]
            print(f"\n📥 Picked TX {tx_id}")

            success = safe_execute(tx)

            if not success:
                update_tx(tx_id, {
                    "status": "FAILED",
                    "reason": "VERIFICATION_OR_EXECUTION_FAILED"
                })

                send_to_dead_letter(tx, "FAILED_VERIFICATION_OR_EXECUTION")

        except Exception as loop_error:
            print(f"💥 Worker loop error: {str(loop_error)}")
            time.sleep(2)


if __name__ == "__main__":
    start_worker()