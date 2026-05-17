# ==============================
# execution_engine.py
# ==============================

from ledger.db import SessionLocal

from ledger.ledger_service import (
    apply_transaction
)

from token_factory import TokenFactory

from tx_verifier import verify_transaction

from execution_queue import (
    update_tx
)

from mirrored_available_state_engine import (
    release_funds
)

from webhook_dispatcher import (
    dispatch_event
)

from audit import log_event


# --------------------------------
# PROCESS EXECUTION
# --------------------------------
def process_execution(tx):

    session = SessionLocal()

    try:

        # --------------------------------
        # PRE-VERIFICATION
        # --------------------------------
        verification = verify_transaction(tx)

        if not verification["valid"]:

            raise Exception(
                f"PRE_VERIFICATION_FAILED: "
                f"{verification['checks']}"
            )

        # --------------------------------
        # RTT VERIFICATION
        # --------------------------------
        payload = tx["payload_rtt"]

        signature = bytes.fromhex(
            tx["rtt_signature"]
        )

        if not TokenFactory.verify(
            payload,
            signature,
            "R1CORE"
        ):

            raise Exception(
                "RTT_VERIFICATION_FAILED"
            )

        # --------------------------------
        # APPLY LEDGER
        # --------------------------------
        apply_transaction(
            session,
            tx
        )

        # --------------------------------
        # GENERATE UTT
        # --------------------------------
        utt = TokenFactory.generate_utt(
            "R1CORE"
        )

        tx["utt"] = utt

        # --------------------------------
        # FINALIZE
        # --------------------------------
        tx["status"] = "SETTLED"

        update_tx(
            tx["tx_id"],
            {
                "status": "SETTLED"
            }
        )

        session.commit()

        log_event(
            "TX_SETTLED",
            tx
        )

        dispatch_event(
            tx,
            "transaction.settled"
        )

        print(
            f"✅ Transaction Settled: "
            f"{tx['tx_id']}"
        )

        return True

    except Exception as e:

        session.rollback()

        error = str(e)

        print(
            f"❌ Execution failed: "
            f"{error}"
        )

        # --------------------------------
        # RELEASE LOCKED FUNDS
        # --------------------------------
        try:

            release_funds(
                session,
                tx["sender_account"],
                tx["gross_amount"]
            )

            session.commit()

            print(
                f"🔓 Released locked funds: "
                f"{tx['gross_amount']}"
            )

        except Exception as rollback_error:

            session.rollback()

            print(
                f"❌ Rollback failed: "
                f"{rollback_error}"
            )

        # --------------------------------
        # MARK FAILED
        # --------------------------------
        tx["status"] = "FAILED"

        tx["failure_reason"] = error

        update_tx(
            tx["tx_id"],
            {
                "status": "FAILED"
            }
        )

        log_event(
            "TX_FAILED",
            tx
        )

        dispatch_event(
            tx,
            "transaction.failed"
        )

        return False

    finally:

        session.close()