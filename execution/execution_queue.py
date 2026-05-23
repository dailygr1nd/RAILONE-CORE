# ==============================
# execution/execution_queue.py
# RailOne Execution Continuity Queue
# Deterministic Execution Orchestrator
# ==============================

import json
import redis

from ledger.db import SessionLocal

from ledger.models import (
    ExecutionThread
)


# ==========================================
# REDIS EXECUTION QUEUES
# ==========================================
r = redis.Redis(

    host="localhost",

    port=6379,

    decode_responses=True
)

EXECUTION_QUEUE = (
    "railone:execution_queue"
)

DEAD_LETTER_QUEUE = (
    "railone:dead_letter"
)


# ==========================================
# STORE EXECUTION THREAD
# ==========================================
def store_execution(execution):

    session = SessionLocal()

    try:

        existing = session.get(

            ExecutionThread,

            execution["utt_id"]
        )

        if existing:

            return

        record = ExecutionThread(

            # --------------------------------
            # EXECUTION CONTINUITY
            # --------------------------------
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

            # --------------------------------
            # EXECUTION ACTORS
            # --------------------------------
            sender_account=
                execution[
                    "sender_account"
                ],

            receiver_account=
                execution[
                    "receiver_account"
                ],

            # --------------------------------
            # EXECUTION VALUE
            # --------------------------------
            amount=
                execution["amount"],

            net_amount=
                execution.get(
                    "net_amount",
                    0
                ),

            fee=
                execution.get(
                    "fee",
                    0
                ),

            profit=
                execution.get(
                    "profit",
                    0
                ),

            currency_from=
                execution[
                    "currency_from"
                ],

            currency_to=
                execution[
                    "currency_to"
                ],

            # --------------------------------
            # EXECUTION STATE
            # --------------------------------
            state=
                execution[
                    "state"
                ],

            replay_generation=
                execution.get(
                    "replay_generation",
                    0
                ),

            lineage_parent=
                execution.get(
                    "lineage_parent"
                )
        )

        session.add(record)

        session.commit()

    finally:

        session.close()


# ==========================================
# UPDATE EXECUTION THREAD
# ==========================================
def update_execution(

    utt_id,

    updates
):

    session = SessionLocal()

    try:

        execution = session.get(

            ExecutionThread,

            utt_id
        )

        if not execution:

            return

        for k, v in updates.items():

            setattr(
                execution,
                k,
                v
            )

        session.commit()

    finally:

        session.close()


# ==========================================
# GET EXECUTION
# ==========================================
def get_execution(utt_id):

    session = SessionLocal()

    try:

        execution = session.get(

            ExecutionThread,

            utt_id
        )

        if not execution:

            return None

        return {

            c.name:
                getattr(
                    execution,
                    c.name
                )

            for c in (
                execution.__table__.columns
            )
        }

    finally:

        session.close()


# ==========================================
# GET ALL EXECUTIONS
# ==========================================
def get_all_executions():

    session = SessionLocal()

    try:

        executions = (

            session.query(
                ExecutionThread
            )

            .all()
        )

        return [

            {

                "utt_id":
                    e.utt_id,

                "rtt_id":
                    e.rtt_id,

                "continuity_uid":
                    e.continuity_uid,

                "sender_account":
                    e.sender_account,

                "receiver_account":
                    e.receiver_account,

                "amount":
                    e.amount,

                "currency_from":
                    e.currency_from,

                "currency_to":
                    e.currency_to,

                "state":
                    e.state,

                "replay_generation":
                    e.replay_generation
            }

            for e in executions
        ]

    finally:

        session.close()


# ==========================================
# QUEUE EXECUTION
# ==========================================
def enqueue_execution(execution):

    r.lpush(

        EXECUTION_QUEUE,

        json.dumps(execution)
    )


# ==========================================
# DEQUEUE EXECUTION
# ==========================================
def dequeue_execution():

    raw = r.rpop(
        EXECUTION_QUEUE
    )

    if not raw:

        return None

    return json.loads(raw)


# ==========================================
# DEAD LETTER RECOVERY
# ==========================================
def send_to_dead_letter(

    execution,

    reason
):

    execution[
        "failure_reason"
    ] = reason

    r.lpush(

        DEAD_LETTER_QUEUE,

        json.dumps(execution)
    )

    print(
        f"☠️ Execution moved to "
        f"dead-letter queue"
    )