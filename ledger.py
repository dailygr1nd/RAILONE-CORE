# ledger.py

import json
import time
import threading
import hashlib
from pathlib import Path

LEDGER_FILE = "ledger.json"


# --------------------------
# LOAD LEDGER FROM DISK
# --------------------------
def load_ledger():
    path = Path(LEDGER_FILE)

    if not path.exists():
        path.write_text("[]")
        return []

    try:
        content = path.read_text().strip()
        return json.loads(content) if content else []
    except json.JSONDecodeError:
        path.write_text("[]")
        return []


# --------------------------
# SAVE LEDGER TO DISK
# --------------------------
def save_ledger(ledger):
    with open(LEDGER_FILE, "w") as f:
        json.dump(ledger, f, indent=4)


# --------------------------
# GLOBAL PERSISTENT LEDGER
# --------------------------
LEDGER = load_ledger()


# --------------------------
# HASH ONLY IMMUTABLE DATA
# --------------------------
def hash_entry(core_entry: dict):
    canonical = str(sorted(core_entry.items())).encode()
    return hashlib.sha256(canonical).hexdigest()


# --------------------------
# BUILD IMMUTABLE CORE
# --------------------------
def build_core(entry):
    return {
        "bank_tx_id": entry["bank_tx_id"],
        "rtt": entry["rtt"],
        "utt": entry["utt"],
        "sender_hash": entry["sender_hash"],
        "receiver_hash": entry["receiver_hash"],
        "amount": entry["amount"],
        "currency": entry["currency"],
        "rail": entry["rail"],
        "timestamp": entry["timestamp"],
        "prev_hash": entry.get("prev_hash"),
    }


# --------------------------
# LOG TRANSACTION
# --------------------------
def log_transaction(
    tx_id,
    rtt,
    utt,
    sender,
    receiver,
    amount,
    currency,
    rail,
):
    global LEDGER

    prev_hash = LEDGER[-1]["hash"] if LEDGER else None

    core = {
        "bank_tx_id": tx_id,
        "rtt": rtt,
        "utt": utt,
        "sender_hash": sender["identity_token"][:12],
        "receiver_hash": receiver["identity_token"][:12],
        "amount": amount,
        "currency": currency,
        "rail": rail,
        "timestamp": time.time(),
        "prev_hash": prev_hash,
    }

    entry = {
        "core": core,
        "hash": hash_entry(core),
        "status": "PENDING",
    }

    LEDGER.append(entry)
    save_ledger(LEDGER)

    threading.Thread(
        target=settle_transaction,
        args=(entry,),
        daemon=True,
    ).start()

    return entry


# --------------------------
# SETTLEMENT SIMULATION
# --------------------------
def settle_transaction(entry, delay=2):
    global LEDGER

    time.sleep(delay)

    entry["status"] = "SETTLED"

    save_ledger(LEDGER)


# --------------------------
# LEDGER INTEGRITY CHECK
# --------------------------
def verify_chain():
    for i, entry in enumerate(LEDGER):
        core = entry["core"]

        expected_hash = hash_entry(core)

        if entry["hash"] != expected_hash:
            return False, f"Tamper detected at index {i}"

        if i > 0:
            if core["prev_hash"] != LEDGER[i - 1]["hash"]:
                return False, f"Broken chain at index {i}"

    return True, "Ledger integrity valid"


# --------------------------
# FIND TRANSACTION
# --------------------------
def find_transaction(utt):
    for entry in LEDGER:
        if entry["core"]["utt"] == utt:
            return entry
    return None


# --------------------------
# VIEW LEDGER
# --------------------------
def view_ledger():
    return LEDGER