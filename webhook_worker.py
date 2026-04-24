import time
from webhook_queue import dequeue_webhook
from webhook_dispatcher import send_webhook

print("📡 Webhook Worker Started")

while True:

    job = dequeue_webhook()

    if not job:
        time.sleep(1)
        continue

    url = job["url"]
    tx = job["tx"]

    success = send_webhook(url, tx, "webhook_secret_dev")

    if not success:
        print("❌ retrying later")
        time.sleep(2)