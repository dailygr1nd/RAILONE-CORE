# ==============================
# execution_engine.py (CRYPTO-STRICT)
# ==============================

from ledger.db import SessionLocal
from ledger.ledger_service import apply_transaction

from token_factory import TokenFactory


def process_execution(tx):

    session = SessionLocal()

    try:
        print(f"🔐 ETK-S: {tx.get('etk_s')}")
        print(f"🔗 RTT: {tx.get('rtt')}")

        # --------------------------------
        # 🔐 1. LOAD RTT DATA (SOURCE OF TRUTH)
        # --------------------------------
        payload_rtt = tx.get("payload_rtt")
        sig_rtt_hex = tx.get("rtt_signature")

        if not payload_rtt or not sig_rtt_hex:
            raise Exception("RTT_DATA_MISSING")

        try:
            signature = bytes.fromhex(sig_rtt_hex)
        except Exception:
            raise Exception("INVALID_RTT_SIGNATURE_FORMAT")

        # --------------------------------
        # 🔐 2. VERIFY SIGNATURE
        # --------------------------------
        if not TokenFactory.verify(
            payload_rtt,
            signature,
            "R1CORE"
        ):
            raise Exception("RTT_SIGNATURE_INVALID")

        # --------------------------------
        # 🔐 3. VERIFY HASH CONSISTENCY
        # --------------------------------
        expected_rtt = TokenFactory._hash(payload_rtt)

        if expected_rtt != tx.get("rtt"):
            raise Exception("RTT_HASH_MISMATCH")

        # --------------------------------
        # 🔐 4. OPTIONAL: STRUCTURAL CHECK
        # --------------------------------
        parts = payload_rtt.split("|")

        if len(parts) != 4 or parts[0] != "RTT":
            raise Exception("RTT_PAYLOAD_INVALID")

        # --------------------------------
        # 💳 5. APPLY LEDGER
        # --------------------------------
        apply_transaction(session, tx)

        # --------------------------------
        # 🧾 6. GENERATE UTT (FINAL IDENTITY)
        # --------------------------------
        utt = TokenFactory.generate_utt("R1CORE")
        tx["utt"] = utt

        # --------------------------------
        # 💾 COMMIT
        # --------------------------------
        session.commit()

        print(f"✅ Execution complete | UTT: {utt}")

        return True

    except Exception as e:
        session.rollback()
        print("❌ Execution failed:", str(e))
        return False

    finally:
        session.close()