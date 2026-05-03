# ==============================
# quote_engine.py (FINAL — PROTOCOL SAFE)
# ==============================

import uuid
import time
import json

from routing import build_route_with_constraints
from pricing_engine import compute_total_pricing
from token_factory import TokenFactory


QUOTE_TTL = 60  # seconds


# --------------------------------
# 🔐 NORMALIZE ROUTE (CRITICAL)
# --------------------------------
def normalize_route(route):
    return {
        "type": route.get("type"),
        "rail": route.get("rail"),
        "cost": round(route.get("cost", 0), 6)
    }


# --------------------------------
# 🚀 MAIN QUOTE GENERATOR
# --------------------------------
def generate_quote(
    sender,
    receiver,
    amount,
    currency_from,
    currency_to
):

    # --------------------------------
    # ROUTE
    # --------------------------------
    route = build_route_with_constraints(
        sender,
        receiver,
        amount,
        currency_from
    )

    if not route:
        return {"error": "NO_ROUTE_AVAILABLE"}

    route = normalize_route(route)

    # --------------------------------
    # PRICING (AUTHORITATIVE)
    # --------------------------------
    is_cross_border = currency_from != currency_to

    pricing = compute_total_pricing(
        amount=amount,
        route=[route],  # ensure consistent structure
        is_cross_border=is_cross_border
    )

    total_fee = pricing["total_revenue"]
    receive_amount = round(amount - total_fee, 2)

    # --------------------------------
    # QUOTE METADATA
    # --------------------------------
    quote_id = f"Q-{uuid.uuid4().hex[:12].upper()}"

    timestamp = int(time.time())
    expires_at = timestamp + QUOTE_TTL

    # --------------------------------
    # 🔐 CANONICAL PAYLOAD (CRITICAL)
    # --------------------------------
    payload = {
        "quote_id": quote_id,
        "amount": amount,
        "currency_from": currency_from,
        "currency_to": currency_to,
        "route": route,
        "pricing": pricing,
        "timestamp": timestamp,
        "expires_at": expires_at
    }

    payload_str = json.dumps(payload, sort_keys=True)

    # --------------------------------
    # 🔐 SIGN QUOTE
    # --------------------------------
    signature = TokenFactory.sign(payload_str, "R1CORE").hex()

    # --------------------------------
    # RETURN (STRICT STRUCTURE)
    # --------------------------------
    return {
        "quote_id": quote_id,
        "route": route,
        "pricing": pricing,

        "send_amount": amount,
        "receive_amount": receive_amount,
        "total_fee": total_fee,

        "timestamp": timestamp,
        "expires_at": expires_at,

        "payload": payload_str,
        "signature": signature
    }