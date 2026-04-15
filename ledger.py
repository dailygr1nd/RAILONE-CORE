# ledger.py

import json
import os
from datetime import datetime, UTC

LEDGER_FILE = "ledger.json"


def _read_ledger():
    if not os.path.exists(LEDGER_FILE):
        return []

    with open(LEDGER_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def write_ledger_entry(tx):
    ledger = _read_ledger()

    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "tx_id": tx["tx_id"],
        "sender_account": tx["sender_account"],
        "receiver_account": tx["receiver_account"],
        "amount": tx["amount"],
        "currency_from": tx["currency_from"],
        "currency_to": tx["currency_to"],
        "status": tx["status"],
        "route": tx["route_result"]["best_route"]["rail"],
        "converted_amount": tx["route_result"]["best_route"]["converted_amount"]
    }

    ledger.append(entry)

    with open(LEDGER_FILE, "w") as f:
        json.dump(ledger, f, indent=2)