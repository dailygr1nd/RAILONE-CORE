# ==============================
# retry_engine.py (FIXED)
# ==============================

import time
import random


MAX_RETRIES = 3


# --------------------------------
# BACKOFF + JITTER
# --------------------------------
def sleep_with_backoff(attempt: int):
    base = 2 ** attempt
    jitter = random.uniform(0, 1)
    time.sleep(base + jitter)


# --------------------------------
# SHOULD RETRY
# --------------------------------
def should_retry(attempt: int) -> bool:
    return attempt < MAX_RETRIES


# --------------------------------
# GET RETRY ROUTES
# --------------------------------
def get_retry_candidates(route_result, failed_rails):

    alternatives = route_result.get("alternatives", [])

    return [
        r for r in alternatives
        if r.get("rail") not in failed_rails
    ]


# --------------------------------
# NEW: SCHEDULE RETRY (ASYNC)
# --------------------------------
def schedule_retry(tx: dict):
    """
    For now: simple log + delay placeholder
    Later: push back into Redis queue with delay
    """

    print(f"🔁 Scheduling retry for {tx['tx_id']}")

    # simulate delay (you will replace with delayed queue later)
    sleep_with_backoff(tx.get("attempts", 1))