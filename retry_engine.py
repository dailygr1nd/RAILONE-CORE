# retry_engine.py

import random
import time

MAX_RETRIES = 3
BASE_DELAY = 0.5  # seconds


def should_retry(attempt: int) -> bool:
    return attempt < MAX_RETRIES


def get_backoff_delay(attempt: int) -> float:
    """
    Exponential backoff with jitter
    """
    base = BASE_DELAY * (2 ** attempt)
    jitter = random.uniform(0, base * 0.3)
    return base + jitter


def sleep_with_backoff(attempt: int):
    delay = get_backoff_delay(attempt)
    time.sleep(delay)