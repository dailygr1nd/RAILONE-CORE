# webhook_engine.py

import requests
import time

WEBHOOKS = {
    "test_client": "http://localhost:9000/webhook"
}


def send_webhook(client_id, payload):

    url = WEBHOOKS.get(client_id)

    if not url:
        return False

    for attempt in range(3):
        try:
            requests.post(url, json=payload, timeout=5)
            return True
        except Exception:
            time.sleep(1)

    return False