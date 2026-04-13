# ledger.py
import time
import threading

# --------------------------
# CENTRAL LEDGER
# --------------------------
LEDGER = []

# --------------------------
# LOG TRANSACTION
# --------------------------
def log_transaction(tx_id, sender, receiver, amount, currency, rail):
    entry = {
        "tx_id": tx_id,
        "sender": sender["username"],
        "receiver": receiver["username"],
        "amount": amount,
        "currency": currency,
        "rail": rail,
        "status": "PENDING"
    }
    LEDGER.append(entry)
    # start settlement simulation in background
    threading.Thread(target=settle_transaction, args=(entry,)).start()
    return entry

# --------------------------
# SIMULATE SETTLEMENT
# --------------------------
def settle_transaction(entry, delay=3):
    """
    Simulate settlement delay (seconds)
    """
    time.sleep(delay)
    entry["status"] = "SETTLED"

# --------------------------
# VIEW LEDGER
# --------------------------
def view_ledger():
    for tx in LEDGER:
        print(f"{tx['tx_id']} | {tx['sender']} -> {tx['receiver']} | {tx['amount']} {tx['currency']} | Rail: {tx['rail']} | Status: {tx['status']}")