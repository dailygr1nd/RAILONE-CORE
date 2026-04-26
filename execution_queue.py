# ==============================
# execution_queue.py (DB + QUEUE)
# ==============================

import json
import redis

from ledger.db import SessionLocal
from ledger.models import Transaction


# --------------------------------
# REDIS QUEUE
# --------------------------------
r = redis.Redis(host="localhost", port=6379, decode_responses=True)

QUEUE_NAME = "railone:tx_queue"
DEAD_LETTER = "railone:dead_letter"


# --------------------------------
# STORE TX (DB)
# --------------------------------
def store_tx(tx):

    session = SessionLocal()

    try:
        existing = session.get(Transaction, tx["tx_id"])

        if existing:
            return

        record = Transaction(
            tx_id=tx["tx_id"],
            sender_account=tx["sender_account"],
            receiver_account=tx["receiver_account"],
            amount=tx["amount"],
            net_amount=tx.get("net_amount", 0),
            currency_from=tx["currency_from"],
            currency_to=tx["currency_to"],
            status=tx["status"],
            fee=tx.get("fee", 0),
            profit=tx.get("profit", 0)
        )

        session.add(record)
        session.commit()

    finally:
        session.close()


# --------------------------------
# UPDATE TX (DB)
# --------------------------------
def update_tx(tx_id, updates):

    session = SessionLocal()

    try:
        tx = session.get(Transaction, tx_id)

        if not tx:
            return

        for k, v in updates.items():
            setattr(tx, k, v)

        session.commit()

    finally:
        session.close()


# --------------------------------
# GET TX
# --------------------------------
def get_tx(tx_id):

    session = SessionLocal()

    try:
        tx = session.get(Transaction, tx_id)

        if not tx:
            return None

        return tx.__dict__

    finally:
        session.close()


# --------------------------------
# GET ALL TX
# --------------------------------
def get_all_tx():

    session = SessionLocal()

    try:
        txs = session.query(Transaction).all()

        return [
            {
                "tx_id": t.tx_id,
                "sender_account": t.sender_account,
                "receiver_account": t.receiver_account,
                "amount": t.amount,
                "currency_from": t.currency_from,
                "currency_to": t.currency_to,
                "status": t.status
            }
            for t in txs
        ]

    finally:
        session.close()


# --------------------------------
# QUEUE OPERATIONS
# --------------------------------
def enqueue_tx(tx):
    r.lpush(QUEUE_NAME, json.dumps(tx))


def dequeue_tx():

    raw = r.rpop(QUEUE_NAME)

    if not raw:
        return None

    return json.loads(raw)


def send_to_dead_letter(tx, reason):

    tx["failure_reason"] = reason

    r.lpush(DEAD_LETTER, json.dumps(tx))