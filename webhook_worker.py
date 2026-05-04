# ==============================
# webhook_worker.py (RETRY + BACKOFF)
# ==============================

import time
import requests
import hmac
import hashlib
import json

from webhook_queue import (
    dequeue_webhook,
    requeue_webhook,
    send_to_dead_letter
)

SECRET = "webhook_secret_dev"
MAX_RETRIES = 5


def sign_payload(payload, timestamp):
    message = f"{timestamp}.{json.dumps(payload, sort_keys=True)}"
    return hmac.new(
        SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()


def send_webhook(url, payload):

    timestamp = str(int(time.time()))
    signature = sign_payload(payload, timestamp)

    headers = {
        "Content-Type": "application/json",
        "X-RailOne-Signature": signature,
        "X-RailOne-Timestamp": timestamp
    }

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=5)
        return res.status_code in [200, 201, 202]
    except Exception:
        return False


print("📡 Webhook Worker Started (RETRY ENABLED)")

while True:

    job = dequeue_webhook()

    if not job:
        time.sleep(1)
        continue

    url = job["url"]
    payload = job["payload"]

    success = send_webhook(url, payload)

    if success:
        print(f"✅ Webhook delivered → {payload['event']}")
        continue

    # --------------------------------
    # RETRY LOGIC
    # --------------------------------
    if job["attempts"] >= MAX_RETRIES:
        print("💀 Dead-lettering webhook")
        send_to_dead_letter(job)
        continue

    # exponential backoff
    delay = 2 ** job["attempts"]
    print(f"🔁 Retry in {delay}s")

    time.sleep(delay)
    requeue_webhook(job)