# ==========================================
# execution/idempotency_store.py
# RailOne Idempotency Registry
# ==========================================

import json
import redis
import time


# ==========================================
# REDIS
# ==========================================
r = redis.Redis(

    host="localhost",

    port=6379,

    decode_responses=True
)


# ==========================================
# DEFAULT TTL
# ==========================================
TTL_SECONDS = 3600


# ==========================================
# KEY
# ==========================================
def _key(

    idempotency_key
):

    return (
        f"idem:{idempotency_key}"
    )


# ==========================================
# LOOKUP
# ==========================================
def check_idempotency(

    idempotency_key
):

    record = r.get(

        _key(
            idempotency_key
        )
    )

    if not record:

        return None

    return json.loads(
        record
    )


# ==========================================
# EXISTS
# ==========================================
def exists(

    idempotency_key
):

    return r.exists(

        _key(
            idempotency_key
        )
    ) == 1


# ==========================================
# STORE
# ==========================================
def store_idempotency(

    idempotency_key,

    response,

    utt_id=None,

    rtt_id=None,

    execution_state=None,

    ttl=TTL_SECONDS
):

    payload = {

        "idempotency_key":
            idempotency_key,

        "utt_id":
            utt_id,

        "rtt_id":
            rtt_id,

        "execution_state":
            execution_state,

        "response":
            response,

        "created_at":
            int(time.time())
    }

    r.setex(

        _key(
            idempotency_key
        ),

        ttl,

        json.dumps(
            payload
        )
    )

    return payload


# ==========================================
# DELETE
# ==========================================
def clear_idempotency(

    idempotency_key
):

    return r.delete(

        _key(
            idempotency_key
        )
    )


# ==========================================
# TTL LOOKUP
# ==========================================
def get_ttl(

    idempotency_key
):

    return r.ttl(

        _key(
            idempotency_key
        )
    )


# ==========================================
# EXTEND TTL
# ==========================================
def extend_ttl(

    idempotency_key,

    ttl=TTL_SECONDS
):

    return r.expire(

        _key(
            idempotency_key
        ),

        ttl
    )