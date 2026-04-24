# ==============================
# idempotency_store.py
# ==============================

import redis
import json

REDIS_HOST = "localhost"
REDIS_PORT = 6379
TTL_SECONDS = 60 * 60  # 1 hour

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


def _key(idem_key: str) -> str:
    return f"idempotency:{idem_key}"


def get_response(idem_key: str):
    data = r.get(_key(idem_key))
    if data:
        return json.loads(data)
    return None


def store_response(idem_key: str, response: dict):
    r.setex(
        _key(idem_key),
        TTL_SECONDS,
        json.dumps(response)
    )