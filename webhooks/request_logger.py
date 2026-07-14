# ==============================
# request_logger.py
# ==============================

import json
from datetime import datetime


LOG_FILE = "requests.log"


def log_request(api_key, endpoint, payload):

    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "api_key": api_key,
        "endpoint": endpoint,
        "payload": payload
    }

    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")