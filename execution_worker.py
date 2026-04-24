# ==============================
# execution_worker.py (FIXED)
# ==============================

from execution_queue import dequeue_tx, send_to_dead_letter
from execution_engine import process_execution


def start_worker():
    print("🚀 Execution Worker Started")

    while True:
        tx = dequeue_tx()

        if not tx:
            continue

        print(f"\n📥 Picked TX {tx['tx_id']}")

        try:
            success = process_execution(tx)

            if not success:
                send_to_dead_letter(tx, "EXECUTION_FAILED")

        except Exception as e:
            print(f"❌ Worker-level failure: {str(e)}")
            send_to_dead_letter(tx, str(e))


if __name__ == "__main__":
    start_worker()