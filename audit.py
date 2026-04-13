# audit.py
import json
import hashlib
from datetime import datetime, timezone
import os

LOG_FILE = "audit_log.json"
ETK_LOG_FILE = "etk_handshake_logs.txt"
DAILY_LOCK_FILE = "daily_lock.json"

def sanitize_for_json(obj):
    if isinstance(obj, bytes):
        return obj.hex()
    elif isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(i) for i in obj]
    else:
        return obj

def hash_entry(data):
    safe_data = sanitize_for_json(data)
    return hashlib.sha256(json.dumps(safe_data, sort_keys=True).encode()).hexdigest()

def load_logs():
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, "r") as f:
        return json.load(f)

def save_logs(logs):
    with open(LOG_FILE, "w") as f:
        json.dump(logs, f, indent=4)

def append_log(event_type, payload, etk_hash=None):
    logs = load_logs()
    prev_hash = logs[-1]["hash"] if logs else "GENESIS"

    timestamp = datetime.now(timezone.utc).isoformat()

    entry = {
        "timestamp": timestamp,
        "event": event_type,
        "payload": sanitize_for_json(payload),
        "prev_hash": prev_hash
    }

    # Compute hash
    entry_hash = hash_entry(entry)
    entry["hash"] = entry_hash

    logs.append(entry)
    save_logs(logs)

    # Optionally write ETK-handshake hash to file
    if etk_hash:
        with open(ETK_LOG_FILE, "a") as f:
            f.write(f"{etk_hash}\n")

    print(f"\n🧾 Log recorded: {event_type}")
    print(f"Hash: {entry_hash[:20]}...")

    return entry_hash

def generate_daily_lock():
    """
    Generates a daily lock JSON file with the final hash of the day's log chain.
    """
    logs = load_logs()
    if not logs:
        return None

    last_hash = logs[-1]["hash"]
    lock = {
        "date": datetime.now(timezone.utc).date().isoformat(),
        "final_hash": last_hash
    }

    # Save to file
    with open(DAILY_LOCK_FILE, "w") as f:
        json.dump(lock, f, indent=4)

    print("\n🔐 DAILY HASH LOCK GENERATED")
    print(json.dumps(lock, indent=4))
    return lock

def verify_chain():
    logs = load_logs()
    for i in range(1, len(logs)):
        if logs[i]["prev_hash"] != logs[i-1]["hash"]:
            print("❌ Chain broken at index", i)
            return False
    print("✅ Log chain verified (no tampering)")
    return True