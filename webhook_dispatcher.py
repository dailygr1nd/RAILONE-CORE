from webhook_queue import enqueue_webhook


def dispatch_event(tx: dict, event_type: str):

    url = tx.get("webhook_url")

    if not url:
        return

    payload = {
        "event": event_type,
        "utt_id": tx["utt_id"],
        "status": tx["status"],
        "amount": tx["amount"],
        "net_amount": tx.get("net_amount"),
        "currency": tx["currency_from"],
        "timestamp": tx["timestamp"]
    }

    enqueue_webhook({
        "url": url,
        "payload": payload
    })