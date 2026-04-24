# ==============================
# audit.py (FILE-BASED + HASH CHAIN)
# ==============================

import json
import hashlib
import os
from datetime import datetime

LOG_FILE = "railone_audit.log"


# --------------------------------
# LOAD LAST HASH
# --------------------------------
def _get_last_hash():
    if not os.path.exists(LOG_FILE):
        return "GENESIS"

    try:
        with open(LOG_FILE, "rb") as f:
            f.seek(0, os.SEEK_END)
            if f.tell() == 0:
                return "GENESIS"

            # read last line
            f.seek(-2, os.SEEK_END)
            while f.read(1) != b"\n":
                f.seek(-2, os.SEEK_CUR)

            last_line = f.readline().decode()
            last_entry = json.loads(last_line)

            return last_entry.get("hash", "GENESIS")

    except Exception:
        return "GENESIS"


# --------------------------------
# SANITIZE PAYLOAD
# --------------------------------
def _sanitize(payload: dict):
    clean = {}

    for k, v in payload.items():

        # remove heavy internal fields
        if k in ["payload_s", "payload_r", "payload_rtt"]:
            continue

        # signatures → mask
        if k == "signatures":
            clean[k] = {kk: "SIGNED" for kk in v}
            continue

        # bytes → convert to string
        if isinstance(v, (bytes, bytearray)):
            clean[k] = v.hex()
            continue

        clean[k] = v

    return clean


# --------------------------------
# HASH GENERATION
# --------------------------------
def _generate_hash(entry, previous_hash):
    raw = json.dumps(entry, sort_keys=True) + previous_hash
    return hashlib.sha256(raw.encode()).hexdigest()


# --------------------------------
# MAIN LOGGER
# --------------------------------
def log_event(event_type: str, payload: dict):

    prev_hash = _get_last_hash()

    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "event": event_type,
        "tx_id": payload.get("tx_id"),
        "data": _sanitize(payload),
        "previous_hash": prev_hash
    }

    entry["hash"] = _generate_hash(entry, prev_hash)

    # append to file
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

    # console output (clean)
    print(f"📊 [{event_type}] tx={entry['tx_id']}")