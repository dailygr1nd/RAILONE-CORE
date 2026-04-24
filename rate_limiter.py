# ==============================
# rate_limiter.py
# ==============================

import redis
import time

r = redis.Redis(host="localhost", port=6379, decode_responses=True)


def _key(api_key: str):
    current_minute = int(time.time() // 60)
    return f"rate:{api_key}:{current_minute}"


def check_rate_limit(api_key: str, limit: int):

    key = _key(api_key)

    current = r.get(key)

    if current is None:
        r.setex(key, 60, 1)
        return True

    if int(current) >= limit:
        return False

    r.incr(key)
    return True