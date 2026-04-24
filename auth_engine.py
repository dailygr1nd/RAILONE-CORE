# ==============================
# auth_engine.py (SECURE)
# ==============================

import hmac
import hashlib
import time

from auth_registry import get_secret


# --------------------------------
# SIGNATURE GENERATION
# --------------------------------
def generate_signature(secret: str, payload: str, timestamp: str):

    message = f"{timestamp}.{payload}".encode()
    secret = secret.encode()

    return hmac.new(secret, message, hashlib.sha256).hexdigest()


# --------------------------------
# VERIFY REQUEST
# --------------------------------
def verify_request(api_key, signature, payload, timestamp):

    secret = get_secret(api_key)

    if not secret:
        return False, "INVALID_API_KEY"

    # --------------------------------
    # TIMESTAMP CHECK (REPLAY PROTECTION)
    # --------------------------------
    now = int(time.time())
    ts = int(timestamp)

    if abs(now - ts) > 300:  # 5 min window
        return False, "REQUEST_EXPIRED"

    # --------------------------------
    # SIGNATURE CHECK
    # --------------------------------
    expected = generate_signature(secret, payload, timestamp)

    if not hmac.compare_digest(expected, signature):
        return False, "INVALID_SIGNATURE"

    return True, None