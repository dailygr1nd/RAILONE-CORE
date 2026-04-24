# ==============================
# webhook_dispatcher.py (QUEUE ONLY)
# ==============================

from webhook_queue import enqueue_webhook


def dispatch_event(tx: dict, event_type: str):

    url = tx.get("webhook_url")

    if not url:
        return

    payload = {
        "event": event_type,
        "tx_id": tx["tx_id"],
        "status": tx["status"],
        "amount": tx["amount"],
        "net_amount": tx.get("net_amount"),
        "currency": tx["currency_from"],
        "timestamp": tx["timestamp"]
    }

    print(f"📡 Queuing webhook → {event_type}")

    enqueue_webhook({
        "url": url,
        "payload": payload
    })