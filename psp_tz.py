# psp_tz.py

import time
import random


def process_transfer(
    amount,
    sender_id,
    receiver_id,
    rtt,
    utt
):
    time.sleep(0.5)

    failure_probability = 0.08

    if random.random() < failure_probability:
        return {
            "success": False,
            "reason": "Mobile money switch unavailable",
            "institution": "MPESA_TZ",
            "institution_tx_id": None
        }

    tx_id = f"MPESA-TZ-{int(time.time() * 1000)}"

    return {
        "success": True,
        "reason": "",
        "institution": "MPESA_TZ",
        "institution_tx_id": tx_id
    }