# audit.py
import json
import hashlib
from datetime import datetime, timezone
import os

LOG_FILE = "audit_log.json"
ETK_LOG_FILE = "etk_handshake_logs.txt"
DAILY_LOCK_FILE = "daily_lock.json"
USER_HASH_SALT = "RAILONE_BANK_DEFENSIBLE_V1"


def sanitize_for_json(obj):
    if isinstance(obj, bytes):
        return obj.hex()
    elif isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(i) for i in obj]
    return obj


def hash_entry(data):
    safe_data = sanitize_for_json(data)
    canonical = json.dumps(
        safe_data,
        sort_keys=True,
        separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def hash_user_identity(nid, name=None, country=None):
    raw = f"{USER_HASH_SALT}|{nid}|{name or ''}|{country or ''}"
    return hashlib.sha256(raw.encode()).hexdigest()


def secure_onboarding_payload(payload):
    payload = dict(payload)

    if "nid" in payload:
        payload["user_hash"] = hash_user_identity(
            payload.get("nid"),
            payload.get("name"),
            payload.get("country")
        )
        payload.pop("nid", None)

    if "name" in payload:
        payload["name_hash"] = hashlib.sha256(
            str(payload["name"]).strip().lower().encode()
        ).hexdigest()
        payload.pop("name", None)

    return payload


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
    clean_payload = sanitize_for_json(payload)

    if event_type == "USER_ONBOARD":
        clean_payload = secure_onboarding_payload(clean_payload)

    entry = {
        "timestamp": timestamp,
        "event": event_type,
        "payload": clean_payload,
        "prev_hash": prev_hash,
        "chain_version": "v2_bank_defensible"
    }

    entry_hash = hash_entry(entry)
    entry["hash"] = entry_hash

    logs.append(entry)
    save_logs(logs)

    if etk_hash:
        with open(ETK_LOG_FILE, "a") as f:
            f.write(f"{etk_hash}\n")

    print(f"\n🧾 Log recorded: {event_type}")
    print(f"Hash: {entry_hash[:20]}...")

    return entry_hash


def generate_daily_lock():
    logs = load_logs()

    if not logs:
        return None

    last_hash = logs[-1]["hash"]

    lock = {
        "date": datetime.now(timezone.utc).date().isoformat(),
        "final_hash": last_hash,
        "chain_verified": verify_chain(silent=True)
    }

    with open(DAILY_LOCK_FILE, "w") as f:
        json.dump(lock, f, indent=4)

    print("\n🔐 DAILY HASH LOCK GENERATED")
    print(json.dumps(lock, indent=4))

    return lock


def verify_chain(silent=False):
    logs = load_logs()

    for i in range(1, len(logs)):
        if logs[i]["prev_hash"] != logs[i - 1]["hash"]:
            if not silent:
                print("❌ Chain broken at index", i)
            return False

        reconstructed = dict(logs[i])
        stored_hash = reconstructed.pop("hash")
        recomputed_hash = hash_entry(reconstructed)

        if stored_hash != recomputed_hash:
            if not silent:
                print("❌ Hash tampering detected at index", i)
            return False

    if not silent:
        print("✅ Log chain verified (no tampering)")

    return True