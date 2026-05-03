# ==============================
# quote_engine.py (PROTOCOL LOCKED)
# ==============================

import uuid
import time
import json

from routing import get_best_rail
from pricing_engine import compute_total_pricing
from token_factory import TokenFactory


QUOTE_TTL = 60


# --------------------------------
# 🔐 NORMALIZE ROUTE
# --------------------------------
def normalize_route(route: dict):
    return {
        "type": route.get("type"),
        "rail": route.get("rail"),
        "cost": round(route.get("cost", 0), 6)
    }


# --------------------------------
# 🚀 GENERATE QUOTE
# --------------------------------
def generate_quote(sender, receiver, amount, currency_from, currency_to):

    # --------------------------------
    # ROUTE
    # --------------------------------
    route = get_best_rail(
        candidate_rails=["MPESA", "BANK_KE", "BANK_UG", "BANK_TZ", "SMOVE"],
        amount=amount,
        currency=currency_from,
        cross_border=(currency_from != currency_to)
    )

    route = normalize_route(route)

    # --------------------------------
    # PRICING
    # --------------------------------
    is_cross_border = currency_from != currency_to

    pricing = compute_total_pricing(
        amount=amount,
        route=[route],
        is_cross_border=is_cross_border
    )

    total_fee = pricing["total_revenue"]
    receive_amount = round(amount - total_fee, 2)

    # --------------------------------
    # QUOTE META
    # --------------------------------
    quote_id = f"Q-{uuid.uuid4().hex[:12].upper()}"

    ts = int(time.time())
    expires_at = ts + QUOTE_TTL

    payload = {
        "quote_id": quote_id,
        "amount": amount,
        "currency_from": currency_from,
        "currency_to": currency_to,
        "route": route,
        "pricing": pricing,
        "timestamp": ts,
        "expires_at": expires_at
    }

    payload_str = json.dumps(payload, sort_keys=True)

    # --------------------------------
    # SIGN
    # --------------------------------
    signature = TokenFactory.sign(payload_str, "R1CORE").hex()

    return {
        "quote_id": quote_id,
        "route": route,
        "pricing": pricing,

        "send_amount": amount,
        "receive_amount": receive_amount,
        "total_fee": total_fee,

        "timestamp": ts,
        "expires_at": expires_at,

        "payload": payload_str,
        "signature": signature
    }