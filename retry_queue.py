import time
from collections import deque

RETRY_QUEUE = deque()


def add_to_retry(tx):
    RETRY_QUEUE.append({
        "tx": tx,
        "attempts": 1,
        "next_try": time.time() + 2
    })


def process_retries(execute_fn):
    now = time.time()

    for item in list(RETRY_QUEUE):
        if now < item["next_try"]:
            continue

        tx = item["tx"]

        result = execute_fn(tx)

        if result.get("status") == "SETTLED":
            RETRY_QUEUE.remove(item)
            continue

        # retry logic
        item["attempts"] += 1

        if item["attempts"] > 3:
            RETRY_QUEUE.remove(item)
            continue

        item["next_try"] = now + (2 ** item["attempts"])