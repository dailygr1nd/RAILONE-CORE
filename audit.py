import json
import hashlib
from pathlib import Path
from datetime import datetime, UTC
from threading import Lock
from typing import Dict, List

AUDIT_PATH = Path("audit_log.json")
AUDIT_LOCK = Lock()


def _load_audit() -> List[Dict]:
    if not AUDIT_PATH.exists():
        return []

    try:
        with AUDIT_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []


def _save_audit(entries: List[Dict]):
    with AUDIT_PATH.open("w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)


def _generate_hash(payload: Dict, previous_hash: str = "") -> str:
    raw = json.dumps(payload, sort_keys=True) + previous_hash
    return hashlib.sha256(raw.encode()).hexdigest()


def log_event(event_type: str, payload: Dict):
    """
    Immutable audit log entry with hash chaining.
    Suitable for regulator replay and forensic tracing.
    """
    with AUDIT_LOCK:
        logs = _load_audit()

        previous_hash = logs[-1]["hash"] if logs else ""

        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": event_type,
            "payload": payload,
        }

        entry["hash"] = _generate_hash(entry, previous_hash)
        entry["previous_hash"] = previous_hash

        logs.append(entry)
        _save_audit(logs)


def get_audit_trail(tx_id: str):
    logs = _load_audit()

    return [
        log for log in logs
        if log.get("payload", {}).get("tx_id") == tx_id
    ]


def verify_chain() -> bool:
    logs = _load_audit()

    previous_hash = ""

    for entry in logs:
        stored_hash = entry.get("hash")

        payload_copy = {
            "timestamp": entry["timestamp"],
            "event": entry["event"],
            "payload": entry["payload"],
        }

        expected_hash = _generate_hash(payload_copy, previous_hash)

        if stored_hash != expected_hash:
            return False

        previous_hash = stored_hash

    return True