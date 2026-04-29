# ==============================
# audit.py (UNIFIED LOGGING)
# ==============================

import json
from datetime import datetime, UTC

LOG_FILE = "railone_audit.log"


def _write(entry: dict):
    entry["timestamp"] = datetime.now(UTC).isoformat()

    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


# --------------------------------
# GENERIC EVENT LOGGER
# --------------------------------
def log_event(event_type: str, data: dict):
    _write({
        "event": event_type,
        "data": data
    })


# --------------------------------
# HANDSHAKE LOGGER (COMPATIBILITY)
# --------------------------------
def append_log(event_type: str, payload: dict):
    _write({
        "event": event_type,
        "payload": payload
    })