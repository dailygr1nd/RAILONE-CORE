# ==============================
# execution_worker.py
# ==============================

import time

from execution_queue import dequeue_tx, send_to_dead_letter
from execution_engine import process_execution
from retry_engine import process_retries


def start_worker():
    print("🚀 Execution Worker Started")

    idle_sleep = 1  # prevents CPU overuse

    while True:
        tx = None  # ensure defined for exception handling

        try:
            # --------------------------------
            # PROCESS RETRIES FIRST
            # --------------------------------
            process_retries()

            # --------------------------------
            # FETCH NEW TX
            # --------------------------------
            tx = dequeue_tx()

            if not tx:
                time.sleep(idle_sleep)
                continue

            tx_id = tx.get("tx_id", "UNKNOWN")
            print(f"\n📥 Picked TX {tx_id}")

            # --------------------------------
            # EXECUTE
            # --------------------------------
            process_execution(tx)

        except Exception as e:
            print("❌ Worker-level failure:", str(e))

            # --------------------------------
            # SAFE DEAD LETTER
            # --------------------------------
            if tx:
                try:
                    send_to_dead_letter(tx, str(e))
                except Exception as dlq_error:
                    print("☠️ Dead-letter failure:", str(dlq_error))

            time.sleep(2)  # prevent crash loop


# --------------------------------
# ENTRY POINT
# --------------------------------
if __name__ == "__main__":
    start_worker()