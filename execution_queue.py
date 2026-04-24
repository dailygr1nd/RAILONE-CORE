# ==============================
# execution_queue.py
# ==============================

import json
import time
import redis

# --------------------------------
# CONFIG
# --------------------------------
REDIS_HOST = "localhost"
REDIS_PORT = 6379
QUEUE_NAME = "railone:tx_queue"
DEAD_LETTER_QUEUE = "railone:dead_letter"

# --------------------------------
# REDIS CONNECTION
# --------------------------------
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True  # store strings instead of bytes
)


# --------------------------------
# ENQUEUE
# --------------------------------
def enqueue_tx(tx: dict):
    """
    Push transaction into queue
    """
    payload = json.dumps(tx)
    redis_client.rpush(QUEUE_NAME, payload)

    print(f"📤 Enqueued TX {tx.get('tx_id')}")


# --------------------------------
# DEQUEUE (BLOCKING)
# --------------------------------
def dequeue_tx(timeout=5):
    """
    Blocking pop (waits for new jobs)
    """
    result = redis_client.blpop(QUEUE_NAME, timeout=timeout)

    if not result:
        return None

    _, payload = result
    tx = json.loads(payload)

    return tx


# --------------------------------
# DEAD LETTER QUEUE
# --------------------------------
def send_to_dead_letter(tx: dict, reason: str):
    """
    Store permanently failed transactions
    """
    tx["dead_letter_reason"] = reason
    tx["failed_at"] = time.time()

    redis_client.rpush(DEAD_LETTER_QUEUE, json.dumps(tx))

    print(f"☠️ TX {tx.get('tx_id')} sent to DEAD LETTER: {reason}")


# --------------------------------
# OPTIONAL: INSPECT QUEUE
# --------------------------------
def get_queue_length():
    return redis_client.llen(QUEUE_NAME)


def get_dead_letter_count():
    return redis_client.llen(DEAD_LETTER_QUEUE)

# --------------------------------
# TX STATE STORAGE
# --------------------------------
TX_STORE = "railone:tx_store"

def store_tx(tx: dict):
    redis_client.hset(TX_STORE, tx["tx_id"], json.dumps(tx))

def get_tx(tx_id: str):
    data = redis_client.hget(TX_STORE, tx_id)
    return json.loads(data) if data else None