# ==============================
# execution/execution_initiator.py
# RailOne Deterministic
# Execution Continuity Initiator
# ==============================

from datetime import (
    datetime,
    UTC
)

import json
import hashlib
import time
import redis

from audit import log_event

from execution.queue.execution_queue import (

    enqueue_execution,

    store_execution
)

from settlement.mirrored_available_state_engine import (

    lock_funds,

    release_funds
)

from ledger.db import SessionLocal

from execution.domain.handshake import run_handshake

from crypto.token_factory import (
    TokenFactory
)

from webhooks.webhook_dispatcher import (
    dispatch_event
)

from execution.events.event_emitter import (
    emit_event
)

from execution.checkpoints.checkpoint_engine import (
    create_checkpoint
)

from execution.execution_verifier import (
    verify_execution
)


# ==========================================
# REDIS
# ==========================================
r = redis.Redis(

    host="localhost",

    port=6379,

    decode_responses=True
)


# ==========================================
# COMPUTE ROUTE HASH
# RTT-bound deterministic proof
# ==========================================
def compute_route_hash(

    route,

    rtt_id
):

    route_str = json.dumps({

        "type":
            route.get("type"),

        "rail":
            route.get("rail"),

        "cost":
            round(
                route.get(
                    "cost",
                    0
                ),
                6
            )

    }, sort_keys=True)

    return hashlib.sha256(

        f"{route_str}|{rtt_id}".encode()

    ).hexdigest()


# ==========================================
# VERIFY QUOTE
# ==========================================
def verify_quote(quote: dict):

    required = [

        "quote_id",

        "route",

        "pricing",

        "expires_at",

        "signature",

        "payload"
    ]

    for field in required:

        if field not in quote:

            return (

                False,

                f"MISSING_{field}"
            )

    # --------------------------------
    # QUOTE EXPIRY
    # --------------------------------
    now = int(time.time())

    if quote["expires_at"] < now:

        return (

            False,

            "QUOTE_EXPIRED"
        )

    # --------------------------------
    # QUOTE SIGNATURE
    # --------------------------------
    try:

        signature = bytes.fromhex(

            quote["signature"]
        )

    except Exception:

        return (

            False,

            "INVALID_SIGNATURE_FORMAT"
        )

    if not TokenFactory.verify(

        quote["payload"],

        signature,

        "R1CORE"
    ):

        return (

            False,

            "INVALID_QUOTE_SIGNATURE"
        )

    return True, None


# ==========================================
# EXECUTION FAILURE HANDLER
# ==========================================
def fail_execution(

    execution: dict,

    reason: str
):

    execution["state"] = (
        "FAILED"
    )

    execution[
        "failure_reason"
    ] = reason

    session = SessionLocal()

    try:

        release_funds(

            session,

            execution[
                "sender_account"
            ],

            execution[
                "gross_amount"
            ]
        )

        session.commit()

    finally:

        session.close()

    # --------------------------------
    # EMIT FAILURE EVENT
    # --------------------------------
    emit_event(

        utt_id=
            execution["utt_id"],

        rtt_id=
            execution.get(
                "rtt_id"
            ),

        continuity_uid=
            execution.get(
                "continuity_uid"
            ),

        event_type=
            "EXECUTION_FAILED",

        previous_state=
            "INIT",

        new_state=
            "FAILED",

        payload={
            "reason": reason
        }
    )

    # --------------------------------
    # STORE FAILED EXECUTION
    # --------------------------------
    store_execution(execution)

    # --------------------------------
    # CREATE CHECKPOINT
    # --------------------------------
    create_checkpoint(

        utt_id=
            execution["utt_id"],

        rtt_id=
            execution.get(
                "rtt_id"
            ),

        continuity_uid=
            execution.get(
                "continuity_uid"
            ),

        checkpoint_state=
            "FAILED",

        snapshot=
            execution
    )

    log_event(

        "EXECUTION_FAILED",

        execution
    )

    dispatch_event(

        execution,

        "execution.failed"
    )

    return execution


# ==========================================
# INITIATE EXECUTION
# ==========================================
def initiate_execution(

    sender_account: str,

    receiver_account: str,

    sender_id: str,

    receiver_id: str,

    continuity_uid: str,

    amount: float,

    sender_currency: str,

    receiver_currency: str,

    quote: dict,

    idempotency_key: str | None = None
):

    gross = float(amount)



    utt_id = TokenFactory.generate_utt(
    sender_id=sender_id,
    receiver_id=receiver_id,
    amount=gross,
    continuity_uid=continuity_uid
    )


    # ==========================================
    # EXECUTION HANDSHAKE
    # ==========================================
    handshake = run_handshake(

    utt_id=utt_id,

    sender_id=sender_id,

    receiver_id=receiver_id,

    amount=gross,

    currency=sender_currency,

    continuity_uid=continuity_uid
    )

    # ==========================================
    # IDEMPOTENCY
    # ==========================================
    if idempotency_key:

        existing = r.get(

            f"idem:{idempotency_key}"
        )

        if existing:

            return {

                "utt_id":
                    existing,

                "status":
                    "DUPLICATE_BLOCKED"
            }

    # ==========================================
    # ETK-S IDEMPOTENCY
    # ==========================================
    etk_key = (

        f"idem:{handshake['etk_s']}"
    )

    if r.get(etk_key):

        return {

            "utt_id":
                r.get(etk_key),

            "status":
                "DUPLICATE_BLOCKED"
        }

    r.set(

        etk_key,

        handshake["utt_id"],

        ex=300
    )

    if idempotency_key:

        r.set(

            f"idem:{idempotency_key}",

            handshake["utt_id"],

            ex=300
        )

    # ==========================================
    # BUILD EXECUTION THREAD
    # ==========================================
    execution = {

        # --------------------------------
        # EXECUTION CONTINUITY
        # --------------------------------
        "utt_id":
            handshake["utt_id"],

        "rtt_id":
            None,

        "continuity_uid":
            continuity_uid,

        # --------------------------------
        # EXECUTION TRUST KEYS
        # --------------------------------
        "etk_s":
            handshake["etk_s"],

        "etk_r":
            handshake["etk_r"],

        # --------------------------------
        # RTT MATERIAL
        # --------------------------------
        "rtt_signature":
            None,

        "payload_rtt":
            None,

        # --------------------------------
        # EXECUTION CONTEXT
        # --------------------------------
        "timestamp":
            datetime.now(
                UTC
            ).isoformat(),

        "sender_account":
            sender_account,

        "receiver_account":
            receiver_account,

        "sender_id":
            sender_id,

        "receiver_id":
            receiver_id,

        # --------------------------------
        # EXECUTION VALUE
        # --------------------------------
        "amount":
            gross,

        "gross_amount":
            gross,

        "currency_from":
            sender_currency,

        "currency_to":
            receiver_currency,

        # --------------------------------
        # EXECUTION STATE
        # --------------------------------
        "state":
            "INIT",

        # --------------------------------
        # REPLAY LINEAGE
        # --------------------------------
        "replay_generation":
            0,

        "lineage_parent":
            None
    }

    # ==========================================
    # EXECUTION START EVENT
    # ==========================================
    emit_event(

        utt_id=
            execution["utt_id"],

        rtt_id=None,

        continuity_uid=
            continuity_uid,

        event_type=
            "EXECUTION_INITIATED",

        previous_state=
            None,

        new_state=
            "INIT"
    )

    log_event(

        "EXECUTION_INITIATED",

        execution
    )

    dispatch_event(

        execution,

        "execution.initiated"
    )

    # ==========================================
    # BASIC VALIDATION
    # ==========================================
    if sender_account == receiver_account:

        return fail_execution(

            execution,

            "SAME_ACCOUNT"
        )

    if gross <= 0:

        return fail_execution(

            execution,

            "INVALID_AMOUNT"
        )

    # ==========================================
    # VERIFY QUOTE
    # ==========================================
    valid, reason = verify_quote(
        quote
    )

    if not valid:

        return fail_execution(
            execution,
            reason
        )

    quote_id = quote["quote_id"]

    # ==========================================
    # QUOTE REPLAY PROTECTION
    # ==========================================
    if r.get(f"quote:{quote_id}"):

        return fail_execution(

            execution,

            "QUOTE_ALREADY_USED"
        )

    r.set(

        f"quote:{quote_id}",

        execution["utt_id"],

        ex=120
    )

    # ==========================================
    # APPLY QUOTE
    # ==========================================
    execution["quote_id"] = (
        quote["quote_id"]
    )

    execution["pricing"] = (
        quote["pricing"]
    )

    execution["fee"] = round(

        quote["total_fee"],

        2
    )

    execution["market_rate"] = (

        quote.get(
            "market_rate",
            1
        )
    )

    execution["fx_rate"] = (

        quote.get(
            "fx_rate",
            1
        )
    )

    execution[
        "net_source_amount"
    ] = (

        quote.get(
            "net_source_amount",
            gross
        )
    )

    execution["net_amount"] = (

        quote["receive_amount"]
    )

    execution["route_result"] = (
        quote["route"]
    )

    # ==========================================
    # RTT GENERATION
    # ==========================================
    rtt_id, sig_rtt, payload_rtt = (

        TokenFactory.generate_rtt_with_quote(

            execution["etk_s"],

            execution["etk_r"],

            execution["utt_id"],

            execution["pricing"],

            quote_id,

            "R1CORE"
        )
    )

    execution["rtt_id"] = (
        rtt_id
    )

    execution["rtt_signature"] = (
        sig_rtt.hex()
    )

    execution["payload_rtt"] = (
        payload_rtt
    )

    # ==========================================
    # ROUTE BINDING
    # ==========================================
    execution["route_hash"] = (

        compute_route_hash(

            execution["route_result"],

            execution["rtt_id"]
        )
    )

    # ==========================================
    # LOCK FUNDS
    # ==========================================
    session = SessionLocal()

    try:

        ok, reason = lock_funds(

            session,

            sender_account,

            gross
        )

        if not ok:

            return fail_execution(

                execution,

                reason
            )

        session.commit()

    except Exception as e:

        session.rollback()

        return fail_execution(

            execution,

            str(e)
        )

    finally:

        session.close()

    # ==========================================
    # VERIFY EXECUTION
    # ==========================================
    verification = verify_execution(
        execution
    )

    if not verification["valid"]:

        return fail_execution(

            execution,

            str(
                verification["checks"]
            )
        )

    # ==========================================
    # CREATE INITIAL CHECKPOINT
    # ==========================================
    create_checkpoint(

        utt_id=
            execution["utt_id"],

        rtt_id=
            execution["rtt_id"],

        continuity_uid=
            continuity_uid,

        checkpoint_state=
            "PENDING",

        snapshot=
            execution
    )

    # ==========================================
    # EXECUTION READY
    # ==========================================
    execution["state"] = (
        "PENDING"
    )

    # ==========================================
    # STORE EXECUTION
    # ==========================================
    store_execution(execution)

    # ==========================================
    # ENQUEUE EXECUTION
    # ==========================================
    enqueue_execution(execution)

    # ==========================================
    # EMIT PENDING EVENT
    # ==========================================
    emit_event(

        utt_id=
            execution["utt_id"],

        rtt_id=
            execution["rtt_id"],

        continuity_uid=
            continuity_uid,

        event_type=
            "EXECUTION_PENDING",

        previous_state=
            "INIT",

        new_state=
            "PENDING"
    )

    dispatch_event(

        execution,

        "execution.pending"
    )

    log_event(

        "EXECUTION_ENQUEUED",

        execution
    )

    return {

        "utt_id":
            execution["utt_id"],

        "rtt_id":
            execution["rtt_id"],

        "status":
            "PENDING",

        "estimated_settlement": {

            "min_minutes": 2,

            "max_minutes": 180
        }
    }