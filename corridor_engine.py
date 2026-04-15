# corridor_engine.py

from routing import classify_rail, get_best_rail
from corridor_fx_model import quote_conversion
from routing_metrics import record_route_result


def build_corridor(sender_account, receiver_account, amount, sender_ccy, receiver_ccy):

    sender_rail = classify_rail(sender_account)
    receiver_rail = classify_rail(receiver_account)

    candidate_rails = [sender_rail, receiver_rail, "SMOVE"]

    best_rail = get_best_rail(candidate_rails, cross_border=(sender_rail != receiver_rail))

    fx_result = quote_conversion(amount, sender_ccy, receiver_ccy)

    route_result = {
        "candidates": [],
        "best_route": {
            "rail": best_rail,
            "type": best_rail,
            "converted_amount": fx_result["converted_amount"],
            "fx_rate": fx_result["fx_rate"]
        }
    }

    for rail in candidate_rails:
        route_result["candidates"].append({
            "rail": rail,
            "type": rail,
            "health": 0,  # placeholder for future ML expansion
            "converted_amount": fx_result["converted_amount"],
            "fx_rate": fx_result["fx_rate"],
            "success_probability": 0.99
        })

    return route_result


def evaluate_route(route_type, success, latency_ms):
    """
    Feedback loop hook
    """
    record_route_result(route_type, success, latency_ms)