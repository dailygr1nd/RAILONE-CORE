# ==============================
# execution_engine.py
# ==============================

from ledger.db import SessionLocal
from ledger.ledger_service import apply_multi_leg_entry

from execution_queue import store_tx
from retry_engine import (
    get_retry_candidates,
    schedule_retry
)

from webhook_dispatcher import dispatch_event


def process_execution(tx: dict):

    session = SessionLocal()

    failed_rails = []
    attempt = tx.get("attempts", 0)

    route = tx.get("route_result", {})

    try:
        while attempt < tx.get("max_attempts", 3):

            if attempt == 0:
                current = route.get("best_route", {})
            else:
                options = get_retry_candidates(route, failed_rails)
                if not options:
                    break
                current = options[0]

            rail = current.get("rail", "SMOVE")

            print(f"⚙️ Attempt {attempt+1} via {rail}")

            try:
                # --------------------------------
                # LEDGER EXECUTION
                # --------------------------------
                apply_multi_leg_entry(
                    session=session,
                    tx=tx,
                    route_type=rail
                )

                session.commit()

                # --------------------------------
                # DEBIT EVENT
                # --------------------------------
                dispatch_event(tx, "TX_DEBITED")

                # --------------------------------
                # FINALIZE
                # --------------------------------
                tx["status"] = "SETTLED"
                tx["settled_via"] = rail

                store_tx(tx)

                dispatch_event(tx, "TX_CREDITED")

                print(f"✅ TX {tx['tx_id']} SETTLED")

                return True

            except Exception as e:
                session.rollback()

                print(f"❌ Attempt failed: {str(e)}")

                failed_rails.append(rail)
                attempt += 1
                tx["attempts"] = attempt

        # --------------------------------
        # FAILURE
        # --------------------------------
        tx["status"] = "FAILED"
        tx["reason"] = "ALL_ROUTES_FAILED"

        store_tx(tx)

        dispatch_event(tx, "TX_FAILED")

        schedule_retry(tx)

        return False

    finally:
        session.close()