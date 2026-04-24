# ==============================
# idempotency_store.py (REDIS)
# ==============================

import redis
import json

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

TTL_SECONDS = 3600  # 1 hour


def _key(k):
    return f"idem:{k}"


def check_idempotency(key: str):
    data = r.get(_key(key))
    return json.loads(data) if data else None


def store_idempotency(key: str, response: dict):
    r.setex(_key(key), TTL_SECONDS, json.dumps(response))