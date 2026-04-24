# execution_worker.py

import time

from execution_queue import QUEUE
from execution_engine import process_pending_tx
from webhook_engine import send_webhook


def run_worker():
    print("🚀 RailOne Execution Worker Started...")

    while True:
        if not QUEUE:
            time.sleep(1)
            continue

        job = QUEUE.pop(0)

        tx = job["tx"]
        route = job["route"]

        print(f"⚙️ Processing TX: {tx['tx_id']}")

        success = process_pending_tx(tx, route)

        # --------------------------------
        # WEBHOOK EMIT
        # --------------------------------
        if success:
            send_webhook(
                client_id=tx.get("metadata", {}).get("client_id", "default"),
                payload={
                    "event": "transaction.settled",
                    "tx_id": tx["tx_id"],
                    "status": "SETTLED"
                }
            )
        else:
            send_webhook(
                client_id=tx.get("metadata", {}).get("client_id", "default"),
                payload={
                    "event": "transaction.failed",
                    "tx_id": tx["tx_id"],
                    "status": "FAILED"
                }
            )