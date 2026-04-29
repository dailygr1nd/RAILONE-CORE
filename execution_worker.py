# ==============================
# execution_worker.py (PROTOCOL ENFORCED)
# ==============================

import time
import redis

from execution_queue import dequeue_tx, send_to_dead_letter, update_tx
from execution_engine import process_execution

from balance_engine import release_funds
from treasury_engine import needs_rebalance, rebalance_pool

from revenue_engine import extract_revenue
from ledger.db import SessionLocal

# 🔥 NEW
from tx_verifier import verify_transaction


# --------------------------------
# REDIS (REPLAY PROTECTION)
# --------------------------------
r = redis.Redis(host="localhost", port=6379, decode_responses=True)


def already_processed(tx_id):
    return r.get(f"processed:{tx_id}") is not None


def mark_processed(tx_id):
    r.setex(f"processed:{tx_id}", 3600, "1")


# --------------------------------
# TREASURY REBALANCING
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
# CORE EXECUTION FLOW
# --------------------------------
def safe_execute(tx):

    tx_id = tx["tx_id"]

    # 🔒 Replay protection (execution-level)
    if already_processed(tx_id):
        print(f"⚠️ Replay blocked: {tx_id}")
        return True

    session = SessionLocal()

    try:
        print(f"\n⚙️ Executing TX {tx_id}")
        print(f"🔐 ETK-S: {tx.get('etk_s')}")
        print(f"🔗 RTT: {tx.get('rtt')}")

        # --------------------------------
        # 🔐 PRE-CHECK: BASIC TOKEN PRESENCE
        # --------------------------------
        if not tx.get("etk_s") or not tx.get("etk_r") or not tx.get("rtt"):
            raise Exception("MISSING_CRYPTO_TOKENS")

        # --------------------------------
        # 1. EXECUTION (RTT VERIFIED INSIDE)
        # --------------------------------
        success = process_execution(tx)

        if not success:
            print(f"❌ TX {tx_id} FAILED (execution)")
            return False

        # --------------------------------
        # 🔥 POST-EXECUTION: FULL VERIFICATION
        # --------------------------------
        import hashlib
        import json

        verification = verify_transaction(tx)

        if not verification["valid"]:
         print("🚨 PROTOCOL VERIFICATION FAILED:")
        for check in verification.get("checks", []):
         print(check)

         raise Exception("POST_EXECUTION_VERIFICATION_FAILED")

      # 🔥 CREATE VERIFICATION HASH
        verification_blob = json.dumps(verification, sort_keys=True)
        verification_hash = hashlib.sha256(verification_blob.encode()).hexdigest()

        tx["verification_hash"] = verification_hash

        print(f"🔍 Verification Hash: {verification_hash[:16]}...")

        # --------------------------------
        # 2. REVENUE EXTRACTION
        # --------------------------------
        try:
            extract_revenue(session, tx)
        except Exception as rev_err:
            print(f"⚠️ Revenue extraction failed: {str(rev_err)}")

        # --------------------------------
        # 3. MARK PROCESSED
        # --------------------------------
        mark_processed(tx_id)

        # --------------------------------
        # 4. UPDATE STATE
        # --------------------------------
        update_tx(tx_id, {
        "status": "SETTLED",
        "utt": tx.get("utt"),
        "verification_hash": tx.get("verification_hash")
      })

        # --------------------------------
        # 5. TREASURY
        # --------------------------------
        run_rebalancing()

        # --------------------------------
        # COMMIT
        # --------------------------------
        session.commit()

        print(f"✅ TX {tx_id} FINALIZED")
        print(f"🧾 UTT: {tx.get('utt')}")

        return True

    except Exception as e:
        print(f"💥 Execution error: {str(e)}")

        session.rollback()

        # --------------------------------
        # 🔥 RELEASE FUNDS (FAILSAFE)
        # --------------------------------
        try:
            release_funds(
                session,
                tx["sender_account"],
                tx.get("gross_amount", tx.get("amount", 0))
            )
            session.commit()
        except Exception as e2:
            print(f"❌ Failed to release funds: {str(e2)}")

        return False

    finally:
        session.close()


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

            tx_id = tx["tx_id"]
            print(f"\n📥 Picked TX {tx_id}")

            success = safe_execute(tx)

            if not success:
                update_tx(tx_id, {
                    "status": "FAILED",
                    "reason": "EXECUTION_FAILED"
                })

                send_to_dead_letter(tx, "EXECUTION_FAILED")

        except Exception as loop_error:
            print(f"💥 Worker loop error: {str(loop_error)}")
            time.sleep(2)


# --------------------------------
# ENTRY
# --------------------------------
if __name__ == "__main__":
    start_worker()