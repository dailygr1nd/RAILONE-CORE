# execution_engine.py

from ledger.db import SessionLocal
from ledger.ledger_service import apply_multi_leg_entry

from retry_engine import should_retry, sleep_with_backoff
from retry_engine import get_retry_candidates


def process_pending_tx(tx, route):

    session = SessionLocal()

    failed_rails = []
    attempt = 0

    try:
        while should_retry(attempt):

            if attempt == 0:
                current_route = route["best_route"]
            else:
                options = get_retry_candidates(route, failed_rails)
                if not options:
                    break
                current_route = options[0]

            rail = current_route.get("rail", "SMOVE")

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

                failed_rails.append(rail)
                attempt += 1

                sleep_with_backoff(attempt)

        return False

    finally:
        session.close()