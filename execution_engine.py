# ==============================
# execution_engine.py (FINAL — HARD VERIFIED)
# ==============================

from ledger.db import SessionLocal
from ledger.ledger_service import apply_transaction

from token_factory import TokenFactory
from tx_verifier import verify_transaction


def process_execution(tx):

    session = SessionLocal()

    try:
        # --------------------------------
        # 🔐 FULL PRE-VERIFICATION
        # --------------------------------
        verification = verify_transaction(tx)

        if not verification["valid"]:
            raise Exception(f"PRE_VERIFICATION_FAILED: {verification['checks']}")

        # --------------------------------
        # 🔐 RTT RE-CHECK (DEFENSE IN DEPTH)
        # --------------------------------
        payload = tx["payload_rtt"]
        signature = bytes.fromhex(tx["rtt_signature"])

        if not TokenFactory.verify(payload, signature, "R1CORE"):
            raise Exception("RTT_VERIFICATION_FAILED")

        # --------------------------------
        # APPLY LEDGER
        # --------------------------------
        apply_transaction(session, tx)

        # --------------------------------
        # FINAL TOKEN
        # --------------------------------
        utt = TokenFactory.generate_utt("R1CORE")
        tx["utt"] = utt
        tx["status"] = "EXECUTING"

        session.commit()

        print("✅ Transaction Settled:", tx["tx_id"])

        return True

    except Exception as e:
        session.rollback()
        print("❌ Execution failed:", str(e))
        return False

    finally:
        session.close()