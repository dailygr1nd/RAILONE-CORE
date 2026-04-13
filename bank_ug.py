# bank_ug.py
import time
import random
from uuid import uuid4

RAIL_NAME = "BANK_UG"
SUPPORTED_CURRENCY = "UGX"
MAX_TX_AMOUNT = 8_000_000
MIN_TX_AMOUNT = 500
BASE_LATENCY_MS = (900, 1500)


def generate_tx_id():
    return f"UG-BANK-{int(time.time())}-{uuid4().hex[:8]}"


def process_transfer(sender_id, receiver_id, amount, currency, metadata=None):
    if currency != SUPPORTED_CURRENCY:
        return {
            "success": False,
            "reason": "Unsupported currency for BANK_UG",
            "rail": RAIL_NAME
        }

    if amount < MIN_TX_AMOUNT:
        return {
            "success": False,
            "reason": "Amount too small",
            "rail": RAIL_NAME
        }

    if amount > MAX_TX_AMOUNT:
        return {
            "success": False,
            "reason": "UGX limit exceeded",
            "rail": RAIL_NAME
        }

    latency = random.randint(*BASE_LATENCY_MS)

    if random.random() > 0.975:
        return {
            "success": False,
            "reason": "Interbank response timeout",
            "rail": RAIL_NAME,
            "latency_ms": latency
        }

    return {
        "success": True,
        "rail": RAIL_NAME,
        "institution_tx_id": generate_tx_id(),
        "latency_ms": latency,
        "settlement_status": "ACCEPTED"
    }