# ==============================
# rate_limiter.py (SAFE)
# ==============================

import time

try:
    import redis
    r = redis.Redis(host="localhost", port=6379, decode_responses=True)
    REDIS_OK = True
except:
    REDIS_OK = False
    r = None


# --------------------------------
# KEY
# --------------------------------
def _key(api_key: str):
    minute = int(time.time() // 60)
    return f"rate:{api_key}:{minute}"


# --------------------------------
# RATE CHECK
# --------------------------------
def check_rate_limit(api_key: str, limit: int):

    # --------------------------------
    # FALLBACK (if Redis down)
    # --------------------------------
    if not REDIS_OK:
        return True  # fail-open (or change to False if strict)

    try:
        key = _key(api_key)

        current = r.get(key)

        if current is None:
            r.setex(key, 60, 1)
            return True

        if int(current) >= limit:
            return False

        r.incr(key)
        return True

    except Exception:
        return True  # fail-open safety