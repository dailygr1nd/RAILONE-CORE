# ==============================
# retry_engine.py
# ==============================

import time
import random


# --------------------------------
# RETRY POLICY
# --------------------------------
MAX_RETRIES = 3
BASE_DELAY = 1  # seconds


def should_retry(attempt: int) -> bool:
    return attempt < MAX_RETRIES


# --------------------------------
# EXPONENTIAL BACKOFF + JITTER
# --------------------------------
def sleep_with_backoff(attempt: int):
    delay = BASE_DELAY * (2 ** attempt)

    # add jitter
    jitter = random.uniform(0, 0.5)
    delay += jitter

    print(f"⏳ Retry in {round(delay,2)}s...")
    time.sleep(delay)


# --------------------------------
# ROUTE FALLBACK LOGIC
# --------------------------------
def get_retry_candidates(route, failed_rails):
    """
    Returns alternative rails excluding failed ones
    """

    candidates = route.get("candidates", [])

    alternatives = [
        r for r in candidates
        if r["rail"] not in failed_rails
    ]

    # sort by score descending
    alternatives.sort(key=lambda x: x["score"], reverse=True)

    return alternatives


# --------------------------------
# OPTIONAL: RETRY QUEUE (future)
# --------------------------------
def process_retries():
    """
    Placeholder for delayed retry queue (Redis later)
    """
    pass