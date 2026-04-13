import time
import threading
import hashlib

LEDGER = []


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
        "prev_hash": entry.get("prev_hash")
    }


# --------------------------
# LOG TRANSACTION (IMMUTABLE CORE + STATE)
# --------------------------
def log_transaction(tx_id, rtt, utt, sender, receiver, amount, currency, rail):

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
        "prev_hash": prev_hash
    }

    entry = {
        "core": core,
        "hash": hash_entry(core),   # ONLY CORE IS HASHED
        "status": "PENDING"
    }

    LEDGER.append(entry)

    threading.Thread(
        target=settle_transaction,
        args=(entry,)
    ).start()

    return entry


# --------------------------
# SETTLEMENT SIMULATION
# --------------------------
def settle_transaction(entry, delay=2):
    time.sleep(delay)
    entry["status"] = "SETTLED"


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
# VIEW LEDGER
# --------------------------
def view_ledger():
    return LEDGER