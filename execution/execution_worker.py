# ==============================
# execution_worker.py
# RailOne Deterministic
# Continuity Execution Worker
# ==============================

import time
import redis

from uuid import uuid4

from execution_queue import (
    dequeue_tx,
    send_to_dead_letter,
    update_tx
)

from execution_engine import (
    process_execution
)

from mirrored_available_state_engine import (
    release_funds
)

from settlement_reference_engine import (
    needs_remirrored_available_state,
    remirrored_available_state_pool
)

from revenue_engine import (
    extract_revenue
)

from tx_verifier import (
    verify_transaction
)

from webhook_dispatcher import (
    dispatch_event
)

from checkpoint_engine import (
    create_checkpoint
)

from execution.state_machine import (
    TransactionContext,
    TransactionState
)

from continuity_reconstructor import (
    reconstruct_continuity
)

from ledger.db import SessionLocal


# ==========================================
# REDIS
# ==========================================
r = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True
)


# ==========================================
# REPLAY PROTECTION
# ==========================================
def already_processed(tx_id):

    return (
        r.get(f"processed:{tx_id}")
        is not None
    )


def mark_processed(tx_id):

    r.setex(
        f"processed:{tx_id}",
        3600,
        "1"
    )


# ==========================================
# CONTINUITY CONTEXT
# ==========================================
def build_context(tx):

    continuity_id = tx.get(
        "continuity_id"
    )

    if not continuity_id:

        continuity_id = (
            f"R1CONT-"
            f"{uuid4().hex[:16].upper()}"
        )

        tx["continuity_id"] = (
            continuity_id
        )

    return TransactionContext(

        tx_id=tx["tx_id"],

        continuity_id=continuity_id,

        amount=tx["amount"],

        currency=tx["currency_from"],

        sender_id=tx["sender_account"],

        receiver_id=tx["receiver_account"]
    )


# ==========================================
# VERIFICATION GATE
# ==========================================
def pre_verify_or_reject(tx):

    result = verify_transaction(tx)

    if not result.get("valid"):

        print(
            f"🚫 VERIFICATION FAILED: "
            f"{tx['tx_id']}"
        )

        for check in result.get(
            "checks",
            []
        ):

            print(f"   - {check}")

        return False, result

    return True, result


# ==========================================
# settlement_reference REBALANCING
# ==========================================
def run_rebalancing():

    session = SessionLocal()

    try:

        for ccy in [
            "KES",
            "TZS",
            "UGX"
        ]:

            if needs_remirrored_available_state(
                session,
                ccy
            ):

                print(
                    f"💰 Rebalancing {ccy}"
                )

                remirrored_available_state_pool(
                    session,
                    ccy
                )

        session.commit()

    except Exception as e:

        print(
            f"⚠️ settlement_reference "
            f"remirrored_available_state "
            f"error: {str(e)}"
        )

        session.rollback()

    finally:

        session.close()


# ==========================================
# SAFE EXECUTION
# ==========================================
def safe_execute(tx):

    tx_id = tx["tx_id"]

    if already_processed(tx_id):

        print(
            f"⚠️ Replay blocked: {tx_id}"
        )

        return True

    # --------------------------------
    # VERIFY
    # --------------------------------
    verified, result = (
        pre_verify_or_reject(tx)
    )

    if not verified:

        dispatch_event(
            tx,
            "transaction.failed"
        )

        return False

    # --------------------------------
    # CONTINUITY CONTEXT
    # --------------------------------
    context = build_context(tx)

    session = SessionLocal()

    try:

        print(
            f"⚙️ Executing TX {tx_id}"
        )

        # --------------------------------
        # IDENTITY VERIFIED
        # --------------------------------
        context.transition(
            TransactionState
            .IDENTITY_VERIFIED
        )

        # --------------------------------
        # INTENT LOCKED (ETK-S)
        # --------------------------------
        context.transition(
        TransactionState
        .INTENT_LOCKED
        )

        # --------------------------------
        # RECEIVER CONFIRMED (ETK-R)
        # --------------------------------
        context.transition(
        TransactionState
        .RECEIVER_CONFIRMED
        )

        # --------------------------------
        # HANDSHAKE VERIFIED (RTT)
        # --------------------------------
        context.transition(
        TransactionState
        .HANDSHAKE_VERIFIED
        )

        # --------------------------------
        # ROUTE COMPUTED
        # --------------------------------
        context.transition(
            TransactionState
            .ROUTE_COMPUTED
        )

        # --------------------------------
        # VALIDATED
        # --------------------------------
        context.transition(
            TransactionState
            .VALIDATED
        )

        # --------------------------------
        # PENDING
        # --------------------------------
        context.transition(
            TransactionState
            .PENDING
        )

        # --------------------------------
        # DISPATCHED
        # --------------------------------
        context.transition(
            TransactionState
            .DISPATCHED
        )

        dispatch_event(
            tx,
            "transaction.executing"
        )

        # --------------------------------
        # EXECUTION STARTED
        # --------------------------------
        context.transition(
            TransactionState
            .EXECUTION_STARTED
        )

        # --------------------------------
        # CHECKPOINT
        # --------------------------------
        create_checkpoint(

            continuity_id=(
                context.continuity_id
            ),

            tx_id=context.tx_id,

            checkpoint_type=(
                "EXECUTION_STARTED"
            ),

            state=context.state.value,

            payload={

                "sender_account":
                    tx["sender_account"],

                "receiver_account":
                    tx["receiver_account"],

                "amount":
                    tx["amount"]
            },

            replay_generation=(
                context.replay_generation
            )
        )

        # --------------------------------
        # EXECUTE
        # --------------------------------
        success = process_execution(tx)

        if not success:

            context.transition(
                TransactionState
                .EXECUTION_FAILED
            )

            dispatch_event(
                tx,
                "transaction.failed"
            )

            return False

        # --------------------------------
        # EXECUTION CONFIRMED
        # --------------------------------
        context.transition(
            TransactionState
            .EXECUTION_CONFIRMED
        )

        # --------------------------------
        # SETTLED
        # --------------------------------
        context.transition(
            TransactionState
            .SETTLED
        )

        # --------------------------------
        # CHECKPOINT
        # --------------------------------
        create_checkpoint(

            continuity_id=(
                context.continuity_id
            ),

            tx_id=context.tx_id,

            checkpoint_type=(
                "SETTLED"
            ),

            state=context.state.value,

            payload={

                "status":
                    "SETTLED",

                "settlement_amount":
                    tx["amount"]
            },

            replay_generation=(
                context.replay_generation
            )
        )

        # --------------------------------
        # FINALIZED
        # --------------------------------
        context.transition(
            TransactionState
            .FINALIZED
        )

        # --------------------------------
        # REVENUE EXTRACTION
        # --------------------------------
        try:

            extract_revenue(
                session,
                tx
            )

        except Exception as rev_err:

            print(
                f"⚠️ Revenue extraction "
                f"failed: {str(rev_err)}"
            )

        # --------------------------------
        # MARK PROCESSED
        # --------------------------------
        mark_processed(tx_id)

        # --------------------------------
        # UPDATE TX
        # --------------------------------
        update_tx(

            tx_id,

            {

                "status":
                    "SETTLED",

                "continuity_id":
                    context.continuity_id
            }
        )

        dispatch_event(
            tx,
            "transaction.completed"
        )

        # --------------------------------
        # settlement_reference
        # --------------------------------
        run_rebalancing()

        session.commit()

        print(
            f"✅ TX {tx_id} SETTLED"
        )

        print(
            f"🔁 Continuity: "
            f"{context.continuity_id}"
        )

        return True

    except Exception as e:

        print(
            f"💥 Execution error: "
            f"{str(e)}"
        )

        session.rollback()

        try:

            context.transition(
                TransactionState
                .FAILED
            )

        except Exception:
            pass

        # --------------------------------
        # RELEASE EXECUTION RESERVATION
        # --------------------------------
        try:

            release_funds(

                session,

                tx["sender_account"],

                tx.get(
                    "gross_amount",
                    tx.get("amount", 0)
                )
            )

            session.commit()

            print(
                "🔓 Execution reservation "
                "released"
            )

        except Exception as e2:

            print(
                f"❌ Failed to release "
                f"funds: {str(e2)}"
            )

        dispatch_event(
            tx,
            "transaction.failed"
        )

        return False

    finally:

        session.close()


# ==========================================
# WORKER LOOP
# ==========================================
def start_worker():

    print(
        "🚀 RailOne Execution Worker "
        "Started"
    )

    while True:

        try:

            tx = dequeue_tx()

            if not tx:

                time.sleep(1)

                continue

            tx_id = tx["tx_id"]

            print(
                f"\n📥 Picked TX {tx_id}"
            )

            success = safe_execute(tx)

            if not success:

                update_tx(

                    tx_id,

                    {

                        "status":
                            "FAILED",

                        "reason":
                            "VERIFICATION_OR_"
                            "EXECUTION_FAILED"
                    }
                )

                send_to_dead_letter(

                    tx,

                    "FAILED_VERIFICATION_"
                    "OR_EXECUTION"
                )

        except Exception as loop_error:

            print(
                f"💥 Worker loop error: "
                f"{str(loop_error)}"
            )

            time.sleep(2)


# ==========================================
# ENTRYPOINT
# ==========================================
if __name__ == "__main__":

    start_worker()