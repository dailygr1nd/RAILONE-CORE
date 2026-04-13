# psp_cross.py
import random
import time
from compliance import check_blacklist, check_tier
from messaging_templates import (
    rollback_sms_template,
    failed_tx_sms_template
)
from audit import append_log

# Local currency mapping
DEST_CURRENCY = {
    "tanzania": "TZS",
    "kenya": "KES",
    "uganda": "UGX",
    "us": "USD"
}

# Base FX rates
BASE_RATES = {
    ("USD", "TZS"): 2500.0,
    ("USD", "KES"): 140.0,
    ("USD", "UGX"): 3800.0,
    ("TZS", "USD"): 1 / 2500.0,
    ("KES", "USD"): 1 / 140.0,
    ("UGX", "USD"): 1 / 3800.0,
}

def get_fx_rate(from_currency, to_currency):
    if from_currency == to_currency:
        return 1.0
    pair = (from_currency, to_currency)
    if pair in BASE_RATES:
        return BASE_RATES[pair]
    inverse_pair = (to_currency, from_currency)
    if inverse_pair in BASE_RATES:
        return 1 / BASE_RATES[inverse_pair]
    raise ValueError(f"FX rate not found for {from_currency} -> {to_currency}")

def generate_fx_offers(amount, source_currency, dest_country):
    dest_currency = DEST_CURRENCY.get(dest_country.lower())
    if not dest_currency:
        return []
    rate = get_fx_rate(source_currency, dest_currency)
    return [{"converted": amount * rate, "rate": rate, "dest_currency": dest_currency}]

def process(amount, route, etk_hash=None):
    """
    Process cross-border transaction.
    route must contain 'sender' and 'receiver' dicts with 'nid', 'name', 'currency', 'balance'.
    """
    sender = route.get("sender", {})
    receiver = route.get("receiver", {})
    rail = route.get("rail", "PSP")
    ttl = route.get("ttl")

    sender_id = sender.get("nid") if isinstance(sender, dict) else sender

    # --------------------------
    # COMPLIANCE CHECKS
    # --------------------------
    ok, error = check_blacklist(sender_id)
    if not ok:
        return failure_response(amount, rail, error, sender, etk_hash)

    ok, error = check_tier(sender, amount)
    if not ok:
        return failure_response(amount, rail, error, sender, etk_hash)

    # --------------------------
    # TTL Check
    # --------------------------
    if ttl and time.time() > ttl:
        return failure_response(amount, rail, "TTL_EXPIRED", sender, etk_hash)

    # --------------------------
    # SIMULATED DELAY
    # --------------------------
    time.sleep(1 + random.random() * 2)

    # --------------------------
    # SIMULATE EXECUTION
    # Wallet rail fails 35% of time, others 2%
    fail_rate = 0.35 if rail.lower() == "wallet" else 0.02
    success = random.random() > fail_rate

    ref_id = route.get("ref_id") or f"UTT-{int(time.time()*1000)}"

    # --------------------------
    # LOG ISO_MESSAGE BEFORE RETURN
    # --------------------------
    iso_payload = {
        "tx_id": ref_id,
        "amount": amount,
        "currency": sender.get("currency", "USD"),
        "handshake_hash": etk_hash
    }
    append_log("ISO_MESSAGE", iso_payload, etk_hash)

    if success:
        bank_payload = {
            "success": True,
            "Status": "Executed",
            "Reason": None,
            "Rail": rail,
            "handshake_hash": etk_hash,
            "converted_amount": amount,
            "forex_rate": 1,
            "destination": "Partner Bank",
            "currency_used": sender.get("currency", "USD")
        }
        append_log("BANK_RESPONSE", bank_payload, etk_hash)
        return {
            "success": True,
            "Status": "Executed",
            "Rail": rail,
            "ref_id": ref_id
        }

    # --------------------------
    # FAILURE -> Rollback simulation
    # --------------------------
    new_balance = sender.get("balance", amount) + amount  # simplistic simulation
    rollback_sms = rollback_sms_template(
        amount=amount,
        currency=sender.get("currency", "USD"),
        ref_id=ref_id,
        new_balance=new_balance
    )
    print(f"\n📲 ROLLBACK SMS\n{rollback_sms}")

    # Log bank response failure
    bank_payload = {
        "success": False,
        "Status": "Failed",
        "Reason": "Cross-border PSP failure",
        "Rail": rail,
        "handshake_hash": etk_hash,
        "ref_id": ref_id
    }
    append_log("BANK_RESPONSE", bank_payload, etk_hash)

    return {
        "success": False,
        "Status": "Failed",
        "Reason": "Cross-border PSP failure",
        "Rail": rail,
        "ref_id": ref_id
    }

def failure_response(amount, rail, reason, sender, etk_hash):
    ref_id = f"UTT-{int(time.time()*1000)}"
    # Log failure
    bank_payload = {
        "success": False,
        "Status": "Failed",
        "Reason": reason,
        "Rail": rail,
        "handshake_hash": etk_hash,
        "ref_id": ref_id
    }
    append_log("BANK_RESPONSE", bank_payload, etk_hash)
    return {
        "success": False,
        "Status": "Failed",
        "Reason": reason,
        "Rail": rail,
        "ref_id": ref_id
    }