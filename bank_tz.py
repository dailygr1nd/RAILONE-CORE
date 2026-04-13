# bank_tz.py
import time
import random
from uuid import uuid4

RAIL_NAME = "BANK_TZ"
SUPPORTED_CURRENCY = "TZS"
MAX_TX_AMOUNT = 10_000_000
MIN_TX_AMOUNT = 100
BASE_LATENCY_MS = (800, 1400)


def generate_tx_id():
    return f"TZ-BANK-{int(time.time())}-{uuid4().hex[:8]}"


def process_transfer(sender_id, receiver_id, amount, currency, metadata=None):
    if currency != SUPPORTED_CURRENCY:
        return {
            "success": False,
            "reason": "Unsupported currency for BANK_TZ",
            "rail": RAIL_NAME
        }

    if amount < MIN_TX_AMOUNT:
        return {
            "success": False,
            "reason": "Amount below threshold",
            "rail": RAIL_NAME
        }

    if amount > MAX_TX_AMOUNT:
        return {
            "success": False,
            "reason": "Exceeds TZS rail limit",
            "rail": RAIL_NAME
        }

    latency = random.randint(*BASE_LATENCY_MS)

    if random.random() > 0.98:
        return {
            "success": False,
            "reason": "Bank settlement queue full",
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