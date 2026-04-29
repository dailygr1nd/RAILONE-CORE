# ==============================
# execution_engine.py (PROTOCOL ENFORCED)
# ==============================

from ledger.db import SessionLocal
from ledger.ledger_service import apply_transaction

from token_factory import TokenFactory


def process_execution(tx):

    session = SessionLocal()

    try:
        # --------------------------------
        # 🔐 VERIFY RTT (CRITICAL)
        # --------------------------------
        expected_payload = f"RTT|{tx['etk_s']}|{tx['etk_r']}|{tx['tx_id']}"

        # NOTE: signature must be stored in tx during handshake
        signature = bytes.fromhex(tx["rtt_signature"])

        if not TokenFactory.verify(
            expected_payload,
            signature,
            "R1CORE"
        ):
            raise Exception("RTT_VERIFICATION_FAILED")

        # --------------------------------
        # APPLY LEDGER
        # --------------------------------
        apply_transaction(session, tx)

        # --------------------------------
        # 🔥 GENERATE UTT (FINAL STATE)
        # --------------------------------
        utt = TokenFactory.generate_utt("R1CORE")
        tx["utt"] = utt

        session.commit()

        return True

    except Exception as e:
        session.rollback()
        print("Execution failed:", str(e))
        return False

    finally:
        session.close()