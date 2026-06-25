# ==============================
# quote_engine.py (FX ENABLED)
# ==============================

import uuid
import time
import json

from ledger.db import SessionLocal

from routing.routing import get_best_rail
from settlement.pricing_engine import compute_total_pricing

from fx_engine import convert
from corridor_fx_model import get_market_rate


QUOTE_TTL = 60


# --------------------------------
# NORMALIZE ROUTE
# --------------------------------
def normalize_route(route: dict):

    return {
        "type": route.get("type"),
        "rail": route.get("rail"),
        "cost": round(route.get("cost", 0), 6)
    }


# --------------------------------
# GENERATE QUOTE
# --------------------------------
def generate_quote(
    sender,
    receiver,
    amount,
    currency_from,
    currency_to
):

    session = SessionLocal()

    try:

        # --------------------------------
        # ROUTE
        # --------------------------------
        route = get_best_rail(
            candidate_rails=[
                "MPESA",
                "BANK_KE",
                "BANK_UG",
                "BANK_TZ",
                "SMOVE"
            ],
            amount=amount,
            currency=currency_from,
            cross_border=(
                currency_from != currency_to
            )
        )

        route = normalize_route(route)

        # --------------------------------
        # PRICING
        # --------------------------------
        is_cross_border = (
            currency_from != currency_to
        )

        pricing = compute_total_pricing(
            amount=amount,
            route=[route],
            is_cross_border=is_cross_border,
            currency_pair=(
                f"{currency_from}_{currency_to}"
            )
        )

        total_fee = round(
            pricing["total_revenue"],
            2
        )

        # --------------------------------
        # NET SOURCE AMOUNT
        # --------------------------------
        net_source_amount = round(
            amount - total_fee,
            2
        )

        if net_source_amount <= 0:

            return {
                "error": "INVALID_NET_AMOUNT"
            }

        # --------------------------------
        # SAME CURRENCY
        # --------------------------------
        if not is_cross_border:

            receive_amount = net_source_amount

            fx_rate = 1
            market_rate = 1

        # --------------------------------
        # CROSS BORDER FX
        # --------------------------------
        else:

            receive_amount, fx_rate = convert(
                net_source_amount,
                currency_from,
                currency_to,
                session
            )

            market_rate = get_market_rate(
                currency_from,
                currency_to
            )

        # --------------------------------
        # QUOTE META
        # --------------------------------
        quote_id = (
            f"Q-{uuid.uuid4().hex[:12].upper()}"
        )

        ts = int(time.time())

        expires_at = ts + QUOTE_TTL

        payload = {
            "quote_id": quote_id,

            "amount": amount,

            "currency_from": currency_from,
            "currency_to": currency_to,

            "route": route,

            "pricing": pricing,

            "net_source_amount": net_source_amount,

            "market_rate": market_rate,
            "fx_rate": fx_rate,

            "receive_amount": receive_amount,

            "timestamp": ts,
            "expires_at": expires_at
        }

        payload_str = json.dumps(
            payload,
            sort_keys=True
        )

        # --------------------------------
        # SIGN
        # --------------------------------
        from crypto.signer import sign_payload

        signature = sign_payload("R1CORE",payload)

        return {

            "quote_id": quote_id,

            "route": route,

            "pricing": pricing,

            "send_amount": amount,

            "net_source_amount": net_source_amount,

            "receive_amount": receive_amount,

            "market_rate": market_rate,
            "fx_rate": fx_rate,

            "currency_from": currency_from,
            "currency_to": currency_to,

            "total_fee": total_fee,

            "timestamp": ts,
            "expires_at": expires_at,

            "payload": payload_str,

            "signature": signature
        }

    finally:
        session.close()