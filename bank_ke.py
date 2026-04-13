# bank_ke.py
import time
import random
from uuid import uuid4

RAIL_NAME = "BANK_KE"
SUPPORTED_CURRENCY = "KES"
MAX_TX_AMOUNT = 5_000_000
MIN_TX_AMOUNT = 10
BASE_LATENCY_MS = (700, 1200)


def generate_tx_id():
    return f"KE-BANK-{int(time.time())}-{uuid4().hex[:8]}"


def process_transfer(sender_id, receiver_id, amount, currency, metadata=None):
    start = time.time()

    if currency != SUPPORTED_CURRENCY:
        return {
            "success": False,
            "reason": "Unsupported currency for BANK_KE",
            "rail": RAIL_NAME
        }

    if amount < MIN_TX_AMOUNT:
        return {
            "success": False,
            "reason": "Amount below minimum transfer threshold",
            "rail": RAIL_NAME
        }

    if amount > MAX_TX_AMOUNT:
        return {
            "success": False,
            "reason": "Transaction exceeds bank limit",
            "rail": RAIL_NAME
        }

    latency = random.randint(*BASE_LATENCY_MS)
    success_probability = 0.985

    if random.random() > success_probability:
        return {
            "success": False,
            "reason": "Temporary banking rail timeout",
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