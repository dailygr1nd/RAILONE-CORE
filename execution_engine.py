# ==============================
# execution_engine.py
# ==============================

from ledger.db import SessionLocal
from ledger.ledger_service import apply_multi_leg_entry

from retry_engine import should_retry, sleep_with_backoff, get_retry_candidates


# --------------------------------
# CORE EXECUTION (ENTRY POINT)
# --------------------------------
def process_execution(tx: dict):
    """
    Entry point called by worker.
    Handles routing + retry logic.
    """

    route = tx.get("route_result")

    if not route:
        raise Exception("NO_ROUTE_FOUND")

    success = process_pending_tx(tx, route)

    if not success:
        raise Exception("ALL_ROUTES_FAILED")

    print(f"✅ TX {tx['tx_id']} SETTLED")


# --------------------------------
# CORE RETRY + SETTLEMENT ENGINE
# --------------------------------
def process_pending_tx(tx, route):

    session = SessionLocal()

    failed_rails = []
    attempt = 0

    try:
        while should_retry(attempt):

            # -----------------------------
            # SELECT ROUTE
            # -----------------------------
            if attempt == 0:
                current_route = route.get("best_route", {})
            else:
                options = get_retry_candidates(route, failed_rails)
                if not options:
                    break
                current_route = options[0]

            rail = current_route.get("rail", "SMOVE")

            print(f"⚙️ Attempt {attempt+1} via {rail}")

            # -----------------------------
            # EXECUTE SETTLEMENT
            # -----------------------------
            try:
                apply_multi_leg_entry(
                    session=session,
                    tx=tx,
                    route_type=rail
                )

                session.commit()
                return True

            except Exception as e:
                session.rollback()

                print(f"❌ Failed on {rail}: {str(e)}")

                failed_rails.append(rail)
                attempt += 1

                sleep_with_backoff(attempt)

        return False

    finally:
        session.close()