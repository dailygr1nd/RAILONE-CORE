# ==============================
# replay_engine.py
# ==============================

import redis
import json

r = redis.Redis(host="localhost", port=6379, db=0)

DEAD_LETTER = "railone:dead_letter"
QUEUE_NAME = "railone:tx_queue"


def replay_failed(limit=10):

    print("🔁 Replaying failed transactions...")

    for _ in range(limit):

        tx = r.rpop(DEAD_LETTER)

        if not tx:
            break

        tx = json.loads(tx)

        if not tx.get("tx_id"):
            continue

        print(f"Replaying TX: {tx['tx_id']}")

        r.lpush(QUEUE_NAME, json.dumps(tx))