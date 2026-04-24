# ==============================
# webhook_dispatcher.py
# ==============================

import requests
import json

WEBHOOK_TIMEOUT = 5


def send_webhook(url: str, payload: dict):
    try:
        response = requests.post(
            url,
            json=payload,
            timeout=WEBHOOK_TIMEOUT
        )
        return response.status_code
    except Exception as e:
        print(f"⚠️ Webhook failed: {str(e)}")
        return None


def dispatch_event(tx: dict, event_type: str):
    """
    event_type: TX_DEBITED | TX_CREDITED | TX_FAILED
    """

    webhook_url = tx.get("webhook_url")

    if not webhook_url:
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

    print(f"📡 Sending webhook → {event_type}")

    send_webhook(webhook_url, payload)