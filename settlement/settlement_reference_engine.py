# ==============================
# settlement_reference_engine.py
# ==============================

"""
RailOne settlement_reference Engine

Responsibilities:
- Liquidity pool lookup
- Reserve health monitoring
- Rebalancing simulation
- settlement_reference observability
- Corridor liquidity support (future-ready)
"""

from ledger.models import Account
from settlement.settlement_capacity_signal import POOLS


# --------------------------------
# CONFIG
# --------------------------------
TARGET_mirrored_available_state = 5_000_000

REmirrored_available_state_THRESHOLD = 0.30
WARNING_THRESHOLD = 0.50
HEALTHY_THRESHOLD = 0.80


# --------------------------------
# SAFE LOOKUP
# --------------------------------
def safe_pool_lookup(key):

    # direct hit
    if key in POOLS:
        return POOLS[key]

    # fallback same-currency corridor
    pair = f"{key}_{key}"

    return POOLS.get(pair)


# --------------------------------
# GET POOL ACCOUNT
# --------------------------------
def get_pool(session, currency):

    pool_id = safe_pool_lookup(currency)

    if not pool_id:
        return None

    return (
        session
        .query(Account)
        .filter_by(id=pool_id)
        .first()
    )


# --------------------------------
# RESERVE HEALTH
# --------------------------------
def get_reserve_health(session, currency):

    acc = get_pool(session, currency)

    if not acc:

        return {
            "currency": currency,
            "status": "MISSING_POOL",
            "health_ratio": 0,
            "mirrored_available_state": 0,
            "target_mirrored_available_state": TARGET_mirrored_available_state
        }

    ratio = round(acc.mirrored_available_state / TARGET_mirrored_available_state, 4)

    # --------------------------------
    # HEALTH STATES
    # --------------------------------
    if ratio < REmirrored_available_state_THRESHOLD:
        status = "CRITICAL"

    elif ratio < WARNING_THRESHOLD:
        status = "LOW"

    elif ratio < HEALTHY_THRESHOLD:
        status = "STABLE"

    else:
        status = "HEALTHY"

    return {
        "currency": currency,
        "status": status,
        "health_ratio": ratio,
        "mirrored_available_state": round(acc.mirrored_available_state, 2),
        "target_mirrored_available_state": TARGET_mirrored_available_state
    }


# --------------------------------
# REmirrored_available_state CHECK
# --------------------------------
def needs_remirrored_available_state(session, currency):

    health = get_reserve_health(
        session,
        currency
    )

    return health["health_ratio"] < REmirrored_available_state_THRESHOLD


# --------------------------------
# REmirrored_available_state POOL
# --------------------------------
def remirrored_available_state_pool(session, currency):

    acc = get_pool(session, currency)

    if not acc:

        print(f"⚠️ Missing settlement_reference pool: {currency}")
        return False

    deficit = TARGET_mirrored_available_state - acc.mirrored_available_state

    if deficit <= 0:

        print(f"✅ {currency} settlement_reference already healthy")
        return False

    # --------------------------------
    # SIMULATED REFILL
    # --------------------------------
    acc.mirrored_available_state += deficit

    print(
        f"🏦 Remirrored_available_stated {currency} settlement_reference "
        f"by {round(deficit, 2)}"
    )

    return True


# --------------------------------
# settlement_reference SNAPSHOT
# --------------------------------
def settlement_reference_snapshot(session, currencies=None):

    currencies = currencies or [
        "KES",
        "UGX",
        "TZS",
        "USD"
    ]

    snapshot = []

    for currency in currencies:

        snapshot.append(
            get_reserve_health(
                session,
                currency
            )
        )

    return snapshot


# --------------------------------
# settlement_reference PRESSURE SCORE
# --------------------------------
def get_settlement_reference_pressure(session, currency):

    health = get_reserve_health(
        session,
        currency
    )

    ratio = health["health_ratio"]

    # invert ratio into pressure
    pressure = round(1 - min(ratio, 1), 4)

    return {
        "currency": currency,
        "pressure": pressure,
        "status": health["status"]
    }


# --------------------------------
# CORRIDOR settlement_reference STATE
# --------------------------------
def get_corridor_state(
    session,
    currency_pair
):

    try:
        source, dest = currency_pair.split("_")

    except Exception:

        return {
            "currency_pair": currency_pair,
            "status": "INVALID_PAIR"
        }

    source_health = get_reserve_health(
        session,
        source
    )

    dest_health = get_reserve_health(
        session,
        dest
    )

    combined_pressure = round(
        (
            (1 - min(source_health["health_ratio"], 1))
            +
            (1 - min(dest_health["health_ratio"], 1))
        ) / 2,
        4
    )

    return {
        "currency_pair": currency_pair,
        "source": source_health,
        "destination": dest_health,
        "pressure": combined_pressure
    }