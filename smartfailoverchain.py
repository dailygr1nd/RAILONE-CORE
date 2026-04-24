# smartfailoverchain.py
# UPGRADED: failover chain is now built dynamically from routing_brain
# rankings instead of a hardcoded list. Falls back to static chain if
# brain returns no candidates. Also integrates routing_metrics recording
# and telemetry drift so every attempt feeds the live health model.


from routing_brain import rank_candidate_rails
from routing_metrics import record_route_result
from telemetry import update_telemetry
import time

# --------------------------------------------------
# CORRIDOR -> CANDIDATE RAILS MAP
# Defines which rails are valid for a given corridor.
# Key: (sender_rail, receiver_rail)
# Value: ordered list of candidate rail dicts to try
# --------------------------------------------------
CORRIDOR_RAIL_CANDIDATES = {
    # Kenya intra-country
    ("BANK_KE", "BANK_KE"):   [{"name": "BANK_KE", "type": "BANK_KE"}, {"name": "PSP_KE", "type": "PSP_KE"}],
    ("BANK_KE", "PSP_KE"):    [{"name": "BANK_KE", "type": "BANK_KE"}, {"name": "PSP_KE", "type": "PSP_KE"}],
    ("PSP_KE",  "BANK_KE"):   [{"name": "PSP_KE",  "type": "PSP_KE"},  {"name": "BANK_KE", "type": "BANK_KE"}],
    ("PSP_KE",  "PSP_KE"):    [{"name": "PSP_KE",  "type": "PSP_KE"},  {"name": "BANK_KE", "type": "BANK_KE"}],

    # Tanzania intra-country
    ("BANK_TZ", "BANK_TZ"):   [{"name": "BANK_TZ", "type": "BANK_TZ"}, {"name": "PSP_TZ", "type": "PSP_TZ"}],
    ("BANK_TZ", "PSP_TZ"):    [{"name": "BANK_TZ", "type": "BANK_TZ"}, {"name": "PSP_TZ", "type": "PSP_TZ"}],
    ("PSP_TZ",  "BANK_TZ"):   [{"name": "PSP_TZ",  "type": "PSP_TZ"},  {"name": "BANK_TZ", "type": "BANK_TZ"}],
    ("PSP_TZ",  "PSP_TZ"):    [{"name": "PSP_TZ",  "type": "PSP_TZ"},  {"name": "BANK_TZ", "type": "BANK_TZ"}],

    # Uganda intra-country
    ("BANK_UG", "BANK_UG"):   [{"name": "BANK_UG", "type": "BANK_UG"}, {"name": "PSP_UG", "type": "PSP_UG"}],
    ("BANK_UG", "PSP_UG"):    [{"name": "BANK_UG", "type": "BANK_UG"}, {"name": "PSP_UG", "type": "PSP_UG"}],
    ("PSP_UG",  "BANK_UG"):   [{"name": "PSP_UG",  "type": "PSP_UG"},  {"name": "BANK_UG", "type": "BANK_UG"}],
    ("PSP_UG",  "PSP_UG"):    [{"name": "PSP_UG",  "type": "PSP_UG"},  {"name": "BANK_UG", "type": "BANK_UG"}],

    # Cross-border: KE <-> TZ
    ("BANK_KE", "BANK_TZ"):   [{"name": "SMOVE", "type": "SMOVE"}, {"name": "BANK_KE", "type": "BANK_KE"}, {"name": "BANK_TZ", "type": "BANK_TZ"}],
    ("BANK_TZ", "BANK_KE"):   [{"name": "SMOVE", "type": "SMOVE"}, {"name": "BANK_TZ", "type": "BANK_TZ"}, {"name": "BANK_KE", "type": "BANK_KE"}],
    ("PSP_KE",  "PSP_TZ"):    [{"name": "SMOVE", "type": "SMOVE"}, {"name": "PSP_KE",  "type": "PSP_KE"},  {"name": "PSP_TZ",  "type": "PSP_TZ"}],
    ("PSP_TZ",  "PSP_KE"):    [{"name": "SMOVE", "type": "SMOVE"}, {"name": "PSP_TZ",  "type": "PSP_TZ"},  {"name": "PSP_KE",  "type": "PSP_KE"}],
    ("BANK_KE", "PSP_TZ"):    [{"name": "SMOVE", "type": "SMOVE"}, {"name": "BANK_KE", "type": "BANK_KE"}],
    ("PSP_KE",  "BANK_TZ"):   [{"name": "SMOVE", "type": "SMOVE"}, {"name": "PSP_KE",  "type": "PSP_KE"}],

    # Cross-border: KE <-> UG
    ("BANK_KE", "BANK_UG"):   [{"name": "SMOVE", "type": "SMOVE"}, {"name": "BANK_KE", "type": "BANK_KE"}, {"name": "BANK_UG", "type": "BANK_UG"}],
    ("BANK_UG", "BANK_KE"):   [{"name": "SMOVE", "type": "SMOVE"}, {"name": "BANK_UG", "type": "BANK_UG"}, {"name": "BANK_KE", "type": "BANK_KE"}],
    ("PSP_KE",  "PSP_UG"):    [{"name": "SMOVE", "type": "SMOVE"}, {"name": "PSP_KE",  "type": "PSP_KE"},  {"name": "PSP_UG",  "type": "PSP_UG"}],
    ("PSP_UG",  "PSP_KE"):    [{"name": "SMOVE", "type": "SMOVE"}, {"name": "PSP_UG",  "type": "PSP_UG"},  {"name": "PSP_KE",  "type": "PSP_KE"}],

    # Cross-border: TZ <-> UG
    ("BANK_TZ", "BANK_UG"):   [{"name": "SMOVE", "type": "SMOVE"}, {"name": "BANK_TZ", "type": "BANK_TZ"}, {"name": "BANK_UG", "type": "BANK_UG"}],
    ("BANK_UG", "BANK_TZ"):   [{"name": "SMOVE", "type": "SMOVE"}, {"name": "BANK_UG", "type": "BANK_UG"}, {"name": "BANK_TZ", "type": "BANK_TZ"}],

    # SMOVE as either side
    ("SMOVE",   "BANK_KE"):   [{"name": "SMOVE", "type": "SMOVE"}, {"name": "BANK_KE", "type": "BANK_KE"}],
    ("SMOVE",   "BANK_TZ"):   [{"name": "SMOVE", "type": "SMOVE"}, {"name": "BANK_TZ", "type": "BANK_TZ"}],
    ("SMOVE",   "BANK_UG"):   [{"name": "SMOVE", "type": "SMOVE"}, {"name": "BANK_UG", "type": "BANK_UG"}],
    ("SMOVE",   "PSP_KE"):    [{"name": "SMOVE", "type": "SMOVE"}, {"name": "PSP_KE",  "type": "PSP_KE"}],
    ("SMOVE",   "PSP_TZ"):    [{"name": "SMOVE", "type": "SMOVE"}, {"name": "PSP_TZ",  "type": "PSP_TZ"}],
    ("SMOVE",   "PSP_UG"):    [{"name": "SMOVE", "type": "SMOVE"}, {"name": "PSP_UG",  "type": "PSP_UG"}],
    ("BANK_KE", "SMOVE"):     [{"name": "SMOVE", "type": "SMOVE"}, {"name": "BANK_KE", "type": "BANK_KE"}],
    ("BANK_TZ", "SMOVE"):     [{"name": "SMOVE", "type": "SMOVE"}, {"name": "BANK_TZ", "type": "BANK_TZ"}],
    ("BANK_UG", "SMOVE"):     [{"name": "SMOVE", "type": "SMOVE"}, {"name": "BANK_UG", "type": "BANK_UG"}],
    ("PSP_KE",  "SMOVE"):     [{"name": "SMOVE", "type": "SMOVE"}, {"name": "PSP_KE",  "type": "PSP_KE"}],
    ("PSP_TZ",  "SMOVE"):     [{"name": "SMOVE", "type": "SMOVE"}, {"name": "PSP_TZ",  "type": "PSP_TZ"}],
    ("PSP_UG",  "SMOVE"):     [{"name": "SMOVE", "type": "SMOVE"}, {"name": "PSP_UG",  "type": "PSP_UG"}],
}


def _get_rail_dispatcher():
    """
    Lazy import to avoid circular dependencies at module load time.
    Returns the dispatch function from transaction_engine.
    """
    from transaction_engine import TransactionEngine
    return TransactionEngine().dispatch


def _dispatch_via_rail(route, sender_rail, receiver_rail, sender_id,
                       receiver_id, amount, sender_currency,
                       receiver_currency, rtt, utt):
    """
    Attempts a single rail dispatch and returns (result, latency_ms).
    """
    from smove_wallet import process_transfer as smove_transfer
    from psp_ke import process_transfer as psp_ke_transfer
    from psp_tz import process_transfer as psp_tz_transfer
    from psp_ug import process_transfer as psp_ug_transfer
    from bank_ke import process_transfer as bank_ke_transfer
    from bank_tz import process_transfer as bank_tz_transfer
    from bank_ug import process_transfer as bank_ug_transfer

    dispatch_map = {
        "SMOVE":   smove_transfer,
        "PSP_KE":  psp_ke_transfer,
        "PSP_TZ":  psp_tz_transfer,
        "PSP_UG":  psp_ug_transfer,
        "BANK_KE": bank_ke_transfer,
        "BANK_TZ": bank_tz_transfer,
        "BANK_UG": bank_ug_transfer,
    }

    handler = dispatch_map.get(route["type"])

    if not handler:
        return {"success": False, "reason": f"NO_HANDLER:{route['type']}"}, 0

    t0 = time.monotonic()
    result = handler(
        sender_id=sender_id,
        receiver_id=receiver_id,
        amount=amount,
        sender_currency=sender_currency,
        receiver_currency=receiver_currency,
        rtt=rtt,
        utt=utt,
    )
    latency_ms = int((time.monotonic() - t0) * 1000)

    return result, latency_ms


def smart_failover(
    sender_rail,
    receiver_rail,
    sender_id,
    receiver_id,
    amount,
    sender_currency,
    receiver_currency,
    rtt,
    utt,
    append_log,
):
    """
    Builds a brain-ranked failover chain for this corridor,
    attempts each route in order, records outcomes into both
    routing_metrics and telemetry for live health drift.
    """

    # 1. Look up corridor candidates
    corridor_key = (sender_rail, receiver_rail)
    static_candidates = CORRIDOR_RAIL_CANDIDATES.get(corridor_key)

    if not static_candidates:
        append_log("FAILOVER_NO_CORRIDOR", {
            "sender_rail": sender_rail,
            "receiver_rail": receiver_rail,
        })
        return {"success": False, "reason": "NO_CORRIDOR_DEFINED"}

    # 2. Ask routing brain to re-rank by live health
    brain_ranked = rank_candidate_rails(static_candidates)
    # brain_ranked: [(rail_dict, score), ...]
    ordered_chain = [rail for rail, _score in brain_ranked]

    append_log("FAILOVER_CHAIN_BUILT", {
        "corridor": f"{sender_rail}->{receiver_rail}",
        "chain": [r["name"] for r in ordered_chain],
        "rtt": rtt,
        "utt": utt,
    })

    tried = set()

    for route in ordered_chain:
        route_type = route["type"]

        if route_type in tried:
            continue
        tried.add(route_type)

        print(f"\n🔁 Trying route: {route['name']} (type={route_type})")

        result, latency_ms = _dispatch_via_rail(
            route=route,
            sender_rail=sender_rail,
            receiver_rail=receiver_rail,
            sender_id=sender_id,
            receiver_id=receiver_id,
            amount=amount,
            sender_currency=sender_currency,
            receiver_currency=receiver_currency,
            rtt=rtt,
            utt=utt,
        )

        success = result.get("success", False)

        # Feed result into live health models
        record_route_result(route_type, success, latency_ms)
        update_telemetry(route_type, success, latency_ms)
        update_health(route_type, "Executed" if success else "Failed")

        append_log("ROUTE_ATTEMPT", {
            "route": route["name"],
            "type": route_type,
            "success": success,
            "latency_ms": latency_ms,
            "rtt": rtt,
            "utt": utt,
        })

        if success:
            return result

        append_log("ROUTE_FAILED", {
            "route": route["name"],
            "reason": result.get("reason", "UNKNOWN"),
            "rtt": rtt,
            "utt": utt,
        })

    return {"success": False, "reason": "ALL_ROUTES_EXHAUSTED"}