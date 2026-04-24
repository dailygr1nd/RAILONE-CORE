# ==============================
# corridor_engine.py (CLEAN + BRIDGE READY)
# ==============================

from rails_config import get_rail, get_currency, supports_currency


# --------------------------------
# BUILD CORRIDOR (CORE ROUTING)
# --------------------------------
def build_corridor(sender, receiver, amount, from_ccy, to_ccy):

    sender_rail = get_rail(sender)
    receiver_rail = get_rail(receiver)

    sender_user = sender.split("-")[1]
    receiver_user = receiver.split("-")[1]

    # --------------------------------
    # DIRECT ROUTE (same currency)
    # --------------------------------
    if from_ccy == to_ccy:
        return {
            "type": "DIRECT",
            "steps": [
                {
                    "leg": 1,
                    "from": sender,
                    "to": receiver,
                    "currency": from_ccy,
                    "action": "TRANSFER"
                }
            ],
            "fx_rate": 1.0,
            "route_meta": {
                "strategy": "DIRECT",
                "rails": [sender_rail]
            }
        }

    # --------------------------------
    # SMOVE BRIDGE ROUTE (FX)
    # --------------------------------
    if supports_currency("SMOVE", from_ccy) and supports_currency("SMOVE", to_ccy):

        smove_sender = f"SMOVE-{sender_user}-{from_ccy}"
        smove_receiver = f"SMOVE-{receiver_user}-{to_ccy}"

        return {
            "type": "SMOVE_BRIDGE",
            "steps": [
                {
                    "leg": 1,
                    "from": sender,
                    "to": smove_sender,
                    "currency": from_ccy,
                    "action": "TRANSFER"
                },
                {
                    "leg": 2,
                    "from": smove_sender,
                    "to": smove_receiver,
                    "currency": f"{from_ccy}->{to_ccy}",
                    "action": "FX"
                },
                {
                    "leg": 3,
                    "from": smove_receiver,
                    "to": receiver,
                    "currency": to_ccy,
                    "action": "TRANSFER"
                }
            ],
            "fx_rate": 1.05,  # mock FX for now
            "route_meta": {
                "strategy": "BRIDGE",
                "rails": ["SMOVE"]
            }
        }

    # --------------------------------
    # NO ROUTE
    # --------------------------------
    return {
        "type": "FAILED",
        "reason": "NO_ROUTE_AVAILABLE",
        "steps": []
    }